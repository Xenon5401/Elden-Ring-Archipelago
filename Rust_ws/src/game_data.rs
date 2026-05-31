use std::collections::HashMap;
use std::path::Path;

#[derive(serde::Deserialize, Clone)]
pub struct ItemData {
    pub id: u32,
    #[serde(rename = "type")]
    pub item_type: u32,
}

pub struct GameData {
    pub datapackage: Option<serde_json::Value>,
    pub item_game_data: HashMap<String, ItemData>,
    flag_to_locs: HashMap<u32, Vec<u32>>,
    item_id_to_name: HashMap<u32, String>,
    datapackage_dirty: bool,
    data_path: String,
}

impl GameData {
    pub fn load(data_path: &str) -> Self {
        let dp_path = Path::new(data_path).join("datapackage_eldenring.json");
        let datapackage = std::fs::read_to_string(&dp_path).ok().and_then(|s| {
            serde_json::from_str(&s).ok()
        });

        let igd_path = Path::new(data_path).join("item_id_to_game_data.json");
        let item_game_data: HashMap<String, ItemData> = std::fs::read_to_string(&igd_path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();

        let mut gd = Self {
            datapackage,
            item_game_data,
            flag_to_locs: HashMap::new(),
            item_id_to_name: HashMap::new(),
            datapackage_dirty: true,
            data_path: data_path.to_string(),
        };
        gd.rebuild_caches();
        gd
    }

    fn rebuild_caches(&mut self) {
        if self.datapackage_dirty {
            self.flag_to_locs.clear();
            self.item_id_to_name.clear();
        }
        if let Some(dp) = &self.datapackage {
            let er = &dp["data"]["games"]["EldenRing"];

            if self.datapackage_dirty {
                let loc_to_flag = er.get("location_to_flag")
                    .or_else(|| er.get("location_id_to_er_flag"))
                    .and_then(|v| v.as_object());

                if let Some(map) = loc_to_flag {
                    for (loc_id_str, flag_val) in map {
                        if let (Some(loc_id), Some(flag_id)) = (
                            loc_id_str.parse::<u32>().ok(),
                            flag_val.as_u64(),
                        ) {
                            self.flag_to_locs
                                .entry(flag_id as u32)
                                .or_default()
                                .push(loc_id);
                        }
                    }
                }

                if let Some(items) = er["item_name_to_id"].as_object() {
                    for (name, id_val) in items {
                        if let Some(id) = id_val.as_u64() {
                            self.item_id_to_name.insert(id as u32, name.clone());
                        }
                    }
                }

                self.datapackage_dirty = false;
            }
        }
    }

    pub fn update_datapackage(&mut self, raw: serde_json::Value) {
        self.datapackage = Some(raw.clone());
        self.datapackage_dirty = true;
        self.rebuild_caches();

        let dp_path = Path::new(&self.data_path).join("datapackage_eldenring.json");
        if let Ok(content) = serde_json::to_string_pretty(&raw) {
            let _ = std::fs::write(&dp_path, content);
        }
    }

    pub fn checksum(&self) -> Option<String> {
        self.datapackage
            .as_ref()
            .and_then(|dp| {
                dp["data"]["games"]["EldenRing"]["checksum"]
                    .as_str()
                    .map(|s| s.to_string())
            })
    }

    pub fn watch_flags(&self) -> Vec<u32> {
        self.flag_to_locs.keys().copied().collect()
    }

    pub fn locs_for_flag(&self, flag_id: u32) -> &[u32] {
        self.flag_to_locs
            .get(&flag_id)
            .map(|v| v.as_slice())
            .unwrap_or_default()
    }

    pub fn item_id_to_name(&self, id: u32) -> Option<&str> {
        self.item_id_to_name.get(&id).map(|s| s.as_str())
    }

    pub fn item_game_data(&self, name: &str) -> Option<&ItemData> {
        self.item_game_data.get(name)
    }
}
