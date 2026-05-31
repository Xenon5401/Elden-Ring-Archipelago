use websocket::ClientBuilder;
use websocket::Message;
use websocket::r#async;
use uuid::Uuid;

const PATH_CONFIG: &str = "/home/xenon/Downloads/ArchipelagoEldenRing/Elden-Ring-Archipelago/Rust_ws/src/elden_ring.yaml";
const PATH_GAMEDATA: &str = "/home/xenon/Downloads/ArchipelagoEldenRing/Elden-Ring-Archipelago/Rust_ws/src/gamedata.json";

fn recv_message_ws(client: &mut websocket::sync::Client<std::net::TcpStream>) -> Option<serde_json::Value> {
    match client.recv_message() {
        Ok(message) => {
            if let websocket::OwnedMessage::Text(text) = message {
                Some(serde_json::from_str(&text).unwrap())
            } else {
                println!("❌ Message reçu n'est pas du texte.");
                None
            }
        }
        Err(e) => {
            println!("❌ Erreur lors de la réception du message : {}", e);
            None
        }
    }
}

fn send_message_ws(client: &mut websocket::sync::Client<std::net::TcpStream>, message: &str) -> bool {
    let msg = Message::text(message.to_string());
    match client.send_message(&msg) {
        Ok(_) => {
            println!("Message envoyé avec succès.");
            true
        }
        Err(e) => {
            println!("❌ Impossible d'envoyer le message : {}", e);
            false
        }
    }
}
fn main() {
    // 1. Lecture et parsing de la config YAML
    let config_str = std::fs::read_to_string(PATH_CONFIG)
        .unwrap_or_else(|e| { println!("❌ Impossible de lire config.yaml : {}", e); return String::new(); }); // (Note: si tu return de la fonction, le String::new() n'est jamais atteint)

    let config: serde_json::Value = serde_yaml::from_str(&config_str)
        .unwrap_or_else(|e| { println!("❌ Impossible de parser config.yaml : {}", e); return serde_json::Value::Null; });

    // 2. Lecture et parsing de gamedata JSON
    let gamedata_str = std::fs::read_to_string(PATH_GAMEDATA)
        .unwrap_or_else(|e| { println!("❌ Impossible de lire gamedata.json : {}", e); return String::new(); });

    let mut gamedata: serde_json::Value = serde_json::from_str(&gamedata_str)
        .unwrap_or_else(|e| { println!("❌ Impossible de parser gamedata.json : {}", e); return serde_json::Value::Null; });

    if gamedata.is_null() {
        gamedata = serde_json::json!({
            "checklist": [],
            "checksum": "",
            "item_name_to_id": {},
            "location_name_to_id": {},
            "location_to_flag": {},
            "uuid": Uuid::new_v4().to_string()
        });
    }

    println!("Tentative de connexion au serveur...");
    // 4. On tente de se connecter sans crash direct
    let client_result = ClientBuilder::new("ws://127.0.0.1:38281")
        .unwrap()
        .connect_insecure();

    match client_result {
        Ok(mut client) => {
            println!("✅ Connecté au serveur WebSocket !");
            // 1. On attend un message du serveur
            let msg = recv_message_ws(&mut client).unwrap();
            println!("📥 Message reçu du serveur : {}",msg);
            // 2. On demande DataPackage du serveur
            if gamedata["checksum"] !=  msg[0]["datapackage_checksums"]["EldenRing"] {
                send_message_ws(&mut client, &serde_json::json!([{"cmd": "GetDataPackage", "games": ["EldenRing"]}]).to_string());
                let getdatapackage = recv_message_ws(&mut client).unwrap();
                println!("📥 DataPackage reçu du serveur");
                gamedata["location_name_to_id"] = getdatapackage[0]["data"]["games"]["EldenRing"]["location_name_to_id"].clone();
                gamedata["item_name_to_id"] = getdatapackage[0]["data"]["games"]["EldenRing"]["item_name_to_id"].clone();
                gamedata["location_to_flag"] = getdatapackage[0]["data"]["games"]["EldenRing"]["location_id_to_er_flag"].clone();
                gamedata["checksum"] = getdatapackage[0]["data"]["games"]["EldenRing"]["checksum"].clone();
                std::fs::write(PATH_GAMEDATA, serde_json::to_string_pretty(&gamedata).unwrap()).expect("Impossible d'écrire gamedata.json");
                return;
            }

            // 3. On envoie notre message de connexion
            let json_message  = serde_json::json!([{
                "cmd": "Connect",
                "password": "",
                "game": "EldenRing",
                "name": "Xenon",
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "version": msg[0]["version"],
                "items_handling": 3,
                "tags": [],
                "slot_data": false
            }]).to_string();
            send_message_ws(&mut client, &json_message);

            
        }

        Err(e) => {
            println!("❌ Erreur de connexion : {}.", e);
        }
    }
}