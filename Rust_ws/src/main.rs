mod ap_client;
mod config;
mod dll_client;
mod game_data;
mod given_locations;

pub struct ApMsg {
    pub base_id: u32,
    pub item_type: u32,
    pub qty: u32,
}

#[tokio::main]
async fn main() {
    let data_path = std::env::current_dir()
        .unwrap_or_default()
        .join("src")
        .to_string_lossy()
        .to_string();

    let config_path = std::path::Path::new(&data_path).join("elden_ring.yaml");
    let cfg = config::load_config(&config_path);

    let game_data = std::sync::Arc::new(tokio::sync::RwLock::new(
        game_data::GameData::load(&data_path),
    ));

    let (dll_tx, mut dll_rx) = tokio::sync::mpsc::unbounded_channel::<dll_client::DllMsg>();
    let (ap_dll_tx, ap_dll_rx) = tokio::sync::mpsc::unbounded_channel::<ApMsg>();

    let gd_ap = game_data.clone();
    let cfg_ap = cfg;
    let data_path_ap = data_path.clone();
    let dll_tx_ap = dll_tx.clone();

    let ap_handle = tokio::spawn(async move {
        ap_client::run(
            cfg_ap,
            data_path_ap,
            gd_ap,
            dll_tx_ap,
            &mut dll_rx,
            ap_dll_tx,
        )
        .await;
    });

    let gd_dll = game_data.clone();
    let data_path_dll = data_path.clone();

    let dll_handle = tokio::spawn(async move {
        dll_client::run(data_path_dll, gd_dll, dll_tx, ap_dll_rx).await;
    });

    let _ = tokio::join!(ap_handle, dll_handle);
}
