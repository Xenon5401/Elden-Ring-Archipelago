use websocket::ClientBuilder;
use websocket::Message;
use websocket::r#async;
use uuid::Uuid;

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
    //lecture des fichier de config
    let config_str = match std::fs::read_to_string("/home/xenon/Downloads/ArchipelagoEldenRing/Elden-Ring-Archipelago/Rust_ws/src/elden_ring.yaml") {
        Ok(contenu) => contenu,
        Err(e) => {
            println!("❌ Impossible de lire config.yaml : {}", e);
            return;
        }
    };
    let config: serde_json::Value = match serde_yaml::from_str(&config_str) {
        Ok(c) => c,
        Err(e) => {
            println!("❌ Impossible de parser config.yaml : {}", e);
            return;
        }
    };
    let gamedata_str = match std::fs::read_to_string("/home/xenon/Downloads/ArchipelagoEldenRing/Elden-Ring-Archipelago/Rust_ws/src/gamedata.json") {
        Ok(contenu) => contenu,
        Err(e) => {
            println!("❌ Impossible de lire gamedata.yaml : {}", e);
            return;
        }
    };
    let gamedata: serde_json::Value = match serde_json::from_str(&gamedata_str) {
        Ok(c) => c,
        Err(e) => {
            println!("❌ Impossible de parser gamedata.yaml : {}", e);
            return;
        }
    };
    println!("Tentative de connexion au serveur...");
    // 1. On tente de se connecter sans crash direct
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
            if ( gamedata["checksum"] != msg[0]["EldenRing"]) {
                send_message_ws(&mut client, &serde_json::json!([{"cmd": "GetDataPackage", "games": ["EldenRing"]}]).to_string());
                let getdatapackage = recv_message_ws(&mut client).unwrap();
                println!("📥 DataPackage reçu du serveur : {}",getdatapackage);
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