# TODO Elden Ring Archipelago Client

## Priorité Haute

- [ ] **Sync / Désync** : Gérer les index mismatch avec `ReceivedItems` → envoyer `Sync` + `LocationChecks`
- [x] **Connexion AP complète** : Handshake complet (RoomInfo → Connect → Connected)
- [x] **Forward items** : Traduire `ReceivedItems` du serveur AP en `/give` vers la DLL

## Items manquants dans item_id_to_game_data.json

- [x] **Poisoned Stone Clump** (id=1841, type=4)
- [x] **Altus Bloom** (id=20681, type=4)
- [x] **Spellproof Pickled Liver** (id=2001120, type=4)
- [x] **Golden Vow (Consumable)** (id=2003170, type=4 — alias de Golden Vow)

## Priorité Moyenne

- [ ] **DeathLink** : Gestion des Bounce packets DeathLink (écouter les morts des autres + envoyer quand le joueur meurt)
- [ ] **Start Inventory** : `items_handling: 0b100` + give des items de départ au spawn
- [ ] **StatusUpdate** : Envoyer `CLIENT_PLAYING` / `CLIENT_GOAL` au serveur AP
- [x] **Reconnexion auto** : Gérer les pertes de connexion AP avec reconnexion automatique
- [ ] **Keep-alive** : Ping périodique pour éviter les timeouts

## Priorité Basse

- [ ] **local_items / non_local_items** : Filtre pour ne pas donner les items locaux
- [ ] **start_hints / start_location_hints** : Intégration système de hints AP
- [ ] **priority_locations** : Système de priorité pour les locations importantes
- [ ] **Options Elden Ring spécifiques** : À définir (remembrances, great runes, etc.)
- [ ] **slot_data** : Récupérer et utiliser les slot_data du serveur AP
- [ ] **DataPackage caching** : Sauvegarder le datapackage AP côté client
- [x] **PrintJSON** : Afficher les messages AP (ItemSend, Chat, Hint, etc.) dans la console
- [ ] **LocationScouts** : Scout les locations avant de les donner pour afficher les noms
