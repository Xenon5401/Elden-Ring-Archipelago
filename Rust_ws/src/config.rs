use std::path::Path;

#[derive(serde::Deserialize)]
#[allow(dead_code)]
pub struct Config {
    pub name: String,
    pub server: String,
    #[serde(default)]
    pub password: String,
    pub game: Option<String>,
    pub flag_file: Option<String>,
    pub items_handling: Option<u8>,
}

pub fn load_config(path: &Path) -> Config {
    let content = std::fs::read_to_string(path)
        .expect("Impossible de lire elden_ring.yaml");
    serde_yaml::from_str(&content)
        .expect("Impossible de parser elden_ring.yaml")
}

pub fn ap_url(config: &Config) -> String {
    let s = &config.server;
    if s.starts_with("ws://") || s.starts_with("wss://") {
        s.clone()
    } else {
        format!("ws://{}/", s)
    }
}
