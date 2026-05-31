use std::collections::HashSet;
use std::path::Path;

pub struct GivenLocations {
    seed: String,
    locations: HashSet<u32>,
    path: String,
}

impl GivenLocations {
    pub fn load(data_path: &str) -> Self {
        let path = Path::new(data_path).join("given_locations.json");
        let path_str = path.to_string_lossy().to_string();

        let (seed, locations) = std::fs::read_to_string(&path)
            .ok()
            .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
            .map(|v| {
                let s = v.get("seed").and_then(|s| s.as_str()).unwrap_or("").to_string();
                let locs = v
                    .get("locations")
                    .and_then(|l| l.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|v| v.as_u64().map(|n| n as u32))
                            .collect()
                    })
                    .unwrap_or_default();
                (s, locs)
            })
            .unwrap_or_default();

        Self { seed, locations, path: path_str }
    }

    fn save(&self) {
        let data = serde_json::json!({
            "seed": self.seed,
            "locations": self.locations.iter().copied().collect::<Vec<_>>(),
        });
        if let Ok(content) = serde_json::to_string(&data) {
            let _ = std::fs::write(&self.path, content);
        }
    }

    pub fn set_seed(&mut self, new_seed: &str) {
        if new_seed != self.seed {
            self.seed = new_seed.to_string();
            self.locations.clear();
            self.save();
        }
    }

    pub fn add(&mut self, loc_id: u32) {
        self.locations.insert(loc_id);
        self.save();
    }

    pub fn has(&self, loc_id: u32) -> bool {
        self.locations.contains(&loc_id)
    }
}
