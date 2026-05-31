use std::sync::Arc;
use std::time::Duration;
use std::collections::HashSet;

use anyhow::Result;
use futures_util::{SinkExt, StreamExt};
use tokio::sync::RwLock;
use tokio_tungstenite::{connect_async, tungstenite::Message};

use crate::game_data::GameData;

pub enum DllMsg {
    LocationChecks(Vec<u32>),
    StatusUpdate(u32),
}

fn is_status_ok(text: &str) -> bool {
    text.contains(r#""status":"ok""#) || text.contains(r#""status":"flag_loot_updated""#)
}

fn is_in_game(text: &str) -> Option<bool> {
    let v: serde_json::Value = serde_json::from_str(text).ok()?;
    v.get("in_game")?.as_bool()
}

fn is_flag_set(text: &str) -> Option<(u32, u8)> {
    let v: serde_json::Value = serde_json::from_str(text).ok()?;
    if v.get("type")?.as_str()? == "flag_set" {
        let flag_id = v.get("flag_id")?.as_u64()? as u32;
        let value = v.get("value")?.as_u64()? as u8;
        Some((flag_id, value))
    } else {
        None
    }
}

pub fn parse_item_name(name: &str) -> (&str, u32) {
    if let Some(pos) = name.rfind(" x") {
        let after = &name[pos + 2..];
        if let Ok(qty) = after.parse::<u32>() {
            return (&name[..pos], qty);
        }
    }
    (name, 1)
}

pub async fn run(
    data_path: String,
    game_data: Arc<RwLock<GameData>>,
    ap_tx: tokio::sync::mpsc::UnboundedSender<DllMsg>,
    mut ap_rx: tokio::sync::mpsc::UnboundedReceiver<crate::ApMsg>,
) {
    loop {
        if let Err(e) = run_inner(&data_path, &game_data, &ap_tx, &mut ap_rx).await {
            eprintln!("[DLL] Error: {e}. Retry in 5s...");
        }
        tokio::time::sleep(Duration::from_secs(5)).await;
    }
}

async fn run_inner(
    _data_path: &str,
    game_data: &Arc<RwLock<GameData>>,
    ap_tx: &tokio::sync::mpsc::UnboundedSender<DllMsg>,
    ap_rx: &mut tokio::sync::mpsc::UnboundedReceiver<crate::ApMsg>,
) -> Result<()> {
    let url = format!("ws://127.0.0.1:12999/ws");
    let (ws_stream, _) = connect_async(&url).await?;
    let (mut write, mut read) = ws_stream.split();

    println!("[DLL] Connecté");
    
    // Wait for in_game
    let mut in_game = false;
    for _ in 0..120 {
        write.send(Message::Text(r#"{"get_status":true}"#.into())).await?;
        if let Some(Ok(Message::Text(resp))) = read.next().await {
            if let Some(ig) = is_in_game(&resp) {
                if ig {
                    in_game = true;
                    break;
                }
            }
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    if !in_game {
        println!("[DLL] Timeout attente jeu (continuant quand même)");
    } else {
        println!("[DLL] Joueur en jeu !");
    }

    // Send CLIENT_PLAYING
    ap_tx.send(DllMsg::StatusUpdate(20))?;

    // Send set_flag_loot
    let flags = {
        let gd = game_data.read().await;
        gd.watch_flags()
    };
    if !flags.is_empty() {
        let loot_msg = serde_json::json!({"set_flag_loot": flags}).to_string();
        for attempt in 1..=3 {
            write.send(Message::Text(loot_msg.clone().into())).await?;
            if let Some(Ok(Message::Text(resp))) = read.next().await {
                if is_status_ok(&resp) {
                    println!("[DLL] Flag loot mis à jour ({} flags)", flags.len());
                    break;
                }
                eprintln!("[DLL] set_flag_loot réponse inattendue: {}", resp);
            }
            if attempt < 3 {
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
        }
    }

    // Main loop
    let mut checked_locs: HashSet<u32> = HashSet::new();
    let mut pending_locs: Vec<u32> = Vec::new();
    let mut flush_timer = tokio::time::interval(Duration::from_millis(200));

    loop {
        tokio::select! {
            _ = flush_timer.tick() => {
                if !pending_locs.is_empty() {
                    let locs = std::mem::take(&mut pending_locs);
                    println!("[DLL] → LocationChecks batch: {} locs", locs.len());
                    ap_tx.send(DllMsg::LocationChecks(locs))?;
                }
            }
            Some(ap_msg) = ap_rx.recv() => {
                let json = serde_json::json!({
                    "base_id": ap_msg.base_id,
                    "type": ap_msg.item_type,
                    "qty": ap_msg.qty,
                });
                write.send(Message::Text(json.to_string().into())).await?;
            }
            ws_msg = read.next() => {
                match ws_msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Some((flag_id, value)) = is_flag_set(&text) {
                            if value == 1 {
                                if flag_id == 510230 {
                                    println!("[DLL] Elden Beast battu ! Envoi CLIENT_GOAL...");
                                    ap_tx.send(DllMsg::StatusUpdate(30))?;
                                }
                                let locs = {
                                    let gd = game_data.read().await;
                                    gd.locs_for_flag(flag_id).to_vec()
                                };
                                let new_locs: Vec<u32> = locs
                                    .into_iter()
                                    .filter(|loc| !checked_locs.contains(loc))
                                    .collect();
                                if !new_locs.is_empty() {
                                    println!("[DLL] Flag {} → locations: {:?}", flag_id, new_locs);
                                    for &loc in &new_locs {
                                        checked_locs.insert(loc);
                                    }
                                    pending_locs.extend(new_locs);
                                }
                            }
                        } else if !is_status_ok(&text) {
                            println!("[DLL] Event: {}", text);
                        }
                    }
                    Some(Ok(Message::Close(_))) | None => {
                        println!("[DLL] Déconnecté");
                        break;
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(())
}
