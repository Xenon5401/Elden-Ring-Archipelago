# TODO Elden Ring Archipelago Client

## Priorité Haute

- [ ] **Sync / Désync** : Gérer les index mismatch avec `ReceivedItems` → envoyer `Sync` + `LocationChecks`
- [x] **Connexion AP complète** : Handshake complet (RoomInfo → Connect → Connected)
- [ ] **Forward items** : Traduire `ReceivedItems` du serveur AP en `/give` vers la DLL

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
- [ ] **PrintJSON** : Afficher les messages AP (ItemSend, Chat, Hint, etc.) dans la console
- [ ] **LocationScouts** : Scout les locations avant de les donner pour afficher les noms
