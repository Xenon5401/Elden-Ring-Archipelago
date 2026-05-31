use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use futures_util::{SinkExt, StreamExt};
use tokio::sync::RwLock;
use tokio_tungstenite::{connect_async, tungstenite::Message};

use crate::config;
use crate::dll_client::DllMsg;
use crate::game_data::GameData;
use crate::given_locations::GivenLocations;

pub async fn run(
    config: config::Config,
    data_path: String,
    game_data: Arc<RwLock<GameData>>,
    dll_tx: tokio::sync::mpsc::UnboundedSender<DllMsg>,
    dll_rx: &mut tokio::sync::mpsc::UnboundedReceiver<DllMsg>,
    ap_dll_tx: tokio::sync::mpsc::UnboundedSender<crate::ApMsg>,
) {
    loop {
        let given_locs = GivenLocations::load(&data_path);
        let uuid = uuid::Uuid::new_v4().to_string();

        if let Err(e) = run_inner(&config, &game_data, &dll_tx, dll_rx, &ap_dll_tx, given_locs, &uuid).await {
            eprintln!("[AP] Error: {e}. Retry in 5s...");
        }
        tokio::time::sleep(Duration::from_secs(5)).await;
    }
}

async fn run_inner(
    config: &config::Config,
    game_data: &Arc<RwLock<GameData>>,
    _dll_tx: &tokio::sync::mpsc::UnboundedSender<DllMsg>,
    dll_rx: &mut tokio::sync::mpsc::UnboundedReceiver<DllMsg>,
    ap_dll_tx: &tokio::sync::mpsc::UnboundedSender<crate::ApMsg>,
    mut given_locs: GivenLocations,
    uuid: &str,
) -> Result<()> {
    let url = config::ap_url(config);
    let (ws_stream, _) = connect_async(&url).await?;
    let (mut write, mut read) = ws_stream.split();

    println!("[AP] Connecté au serveur {}", url);

    // 1. Receive RoomInfo
    let room_info = match read.next().await {
        Some(Ok(Message::Text(text))) => {
            let parsed: Vec<serde_json::Value> = serde_json::from_str(&text)?;
            parsed.into_iter().next().unwrap_or_default()
        }
        _ => return Err(anyhow::anyhow!("Pas de RoomInfo reçu")),
    };

    println!("[AP] RoomInfo reçu");
    let server_version = room_info["version"].clone();
    let seed_name = room_info["seed_name"].as_str().unwrap_or("").to_string();
    let server_checksum = room_info["datapackage_checksums"]["EldenRing"]
        .as_str()
        .map(|s| s.to_string());

    given_locs.set_seed(&seed_name);

    // 2. Check/update datapackage
    let needs_update = {
        let gd = game_data.read().await;
        gd.datapackage.is_none() || gd.checksum() != server_checksum
    };

    if needs_update {
        println!("[AP] Demande du DataPackage...");
        let req = r#"[{"cmd":"GetDataPackage","games":["EldenRing"]}]"#;
        write.send(Message::Text(req.into())).await?;

        if let Some(Ok(Message::Text(text))) = read.next().await {
            let parsed: Vec<serde_json::Value> = serde_json::from_str(&text)?;
            if let Some(dp) = parsed.into_iter().next() {
                let mut gd = game_data.write().await;
                gd.update_datapackage(dp);
                println!("[AP] DataPackage mis à jour");
            }
        }
    }

    // 3. Send Connect
    let items_handling = config.items_handling.unwrap_or(3);
    let connect_msg = serde_json::json!([{
        "cmd": "Connect",
        "password": config.password,
        "game": "EldenRing",
        "name": config.name,
        "uuid": uuid,
        "version": server_version,
        "items_handling": items_handling,
        "tags": [],
        "slot_data": false,
    }]);
    write.send(Message::Text(connect_msg.to_string().into())).await?;
    println!("[AP] Connect envoyé");

    // 4. Receive Connected
    let connected = match read.next().await {
        Some(Ok(Message::Text(text))) => {
            let parsed: Vec<serde_json::Value> = serde_json::from_str(&text)?;
            parsed.into_iter().next().unwrap_or_default()
        }
        _ => return Err(anyhow::anyhow!("Pas de réponse à Connect")),
    };

    if connected["cmd"] == "ConnectionRefused" {
        let errors = connected.get("errors");
        eprintln!("[AP] Connexion refusée: {:?}", errors);
        return Err(anyhow::anyhow!("ConnectionRefused"));
    }

    let team = connected["team"].as_u64().unwrap_or(0);
    let slot = connected["slot"].as_u64().unwrap_or(0);
    println!("[AP] Connecté! Team={team} Slot={slot}");

    // 5. Main event loop
    let mut received_idx: u64 = 0;

    loop {
        tokio::select! {
            Some(msg) = dll_rx.recv() => {
                let json = match msg {
                    DllMsg::LocationChecks(locs) => {
                        serde_json::json!([{"cmd": "LocationChecks", "locations": locs}])
                    }
                    DllMsg::StatusUpdate(status) => {
                        serde_json::json!([{"cmd": "StatusUpdate", "status": status}])
                    }
                };
                write.send(Message::Text(json.to_string().into())).await?;
            }
            ws_msg = read.next() => {
                match ws_msg {
                    Some(Ok(Message::Text(text))) => {
                        let parsed: Vec<serde_json::Value> = serde_json::from_str(&text)?;
                        for msg in parsed {
                            let cmd = msg["cmd"].as_str().unwrap_or("");
                            match cmd {
                                "ReceivedItems" => {
                                    let items = msg["items"].as_array().cloned().unwrap_or_default();
                                    let index = msg["index"].as_u64().unwrap_or(0);

                                    for (i, item) in items.iter().enumerate() {
                                        let idx = index + i as u64;
                                        if idx < received_idx {
                                            continue;
                                        }
                                        let item_id = match item["item"].as_u64() {
                                            Some(id) => id as u32,
                                            None => continue,
                                        };
                                        let location_id = match item["location"].as_u64() {
                                            Some(id) => id as u32,
                                            None => continue,
                                        };

                                        if given_locs.has(location_id) {
                                            continue;
                                        }

                                        let name = {
                                            let gd = game_data.read().await;
                                            gd.item_id_to_name(item_id).map(|s| s.to_string())
                                        };

                                        if let Some(name) = name {
                                            let (base_name, qty) = crate::dll_client::parse_item_name(&name);
                                            let gd = {
                                                let gd = game_data.read().await;
                                                gd.item_game_data(base_name).cloned()
                                            };
                                            if let Some(item_data) = gd {
                                                let msg = crate::ApMsg {
                                                    base_id: item_data.id,
                                                    item_type: item_data.item_type,
                                                    qty,
                                                };
                                                ap_dll_tx.send(msg)?;
                                                given_locs.add(location_id);
                                                println!("[AP] [{idx}] {name} → give (qty={qty})");
                                            } else {
                                                println!("[AP] [{idx}] {name}: pas de game data, skip");
                                            }
                                        } else {
                                            println!("[AP] [{idx}] item_id={item_id} inconnu, skip");
                                        }
                                        received_idx = idx + 1;
                                    }
                                }
                                "RoomUpdate" => {
                                    let missing = msg["missing_locations"].as_array().map(|a| a.len()).unwrap_or(0);
                                    let checked = msg["checked_locations"].as_array().map(|a| a.len()).unwrap_or(0);
                                    println!("[AP] RoomUpdate: missing={missing} checked={checked}");
                                }
                                "PrintJSON" => {
                                    if let Some(data) = msg.get("data") {
                                        println!("[AP] PrintJSON: {data}");
                                    }
                                }
                                _ => {
                                    if !cmd.is_empty() {
                                        println!("[AP] Event: cmd={cmd}");
                                    }
                                }
                            }
                        }
                    }
                    Some(Ok(Message::Close(_))) | None => {
                        println!("[AP] Déconnecté du serveur");
                        break;
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(())
}
