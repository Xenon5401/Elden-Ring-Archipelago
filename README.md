# Elden Ring Archipelago

Client Archipelago pour Elden Ring. Reçoit des items depuis un multiworld Archipelago et les give dans le jeu via hooking mémoire.

> **Développement sur Elden Ring v1.12.**  
> Les AOB patterns peuvent ne pas fonctionner sur d'autres versions — il faudra probablement les mettre à jour.

---

## Architecture

```
┌─────────────────────┐       WebSocket (json)         ┌──────────────────────┐
│  Elden Ring         │  ──────────────────────────►   │  archipelago.py      │
│  (myserver.dll)     │  ◄──────────────────────────   │  (client Python)     │
│                     │       /give items              │                      │
│  - AOB scan         │                                │  - lit map_items.json│
│  - Hook AddItem     │                                │  - se connecte à AP  │
│  - Hook EventFlag   │                                └──────────────────────┘
│  - Serveur HTTP/WS  │
└─────────────────────┘
```

### Comportement

1. `myserver.dll` est injectée dans `eldenring.exe`.
2. Le DLL scanne la mémoire du jeu pour trouver les fonctions `AddItem` et `SetEventFlag` (via AOB patterns).
3. Il installe des hooks (inline detours) sur ces fonctions.
4. Un serveur HTTP/WebSocket écoute sur `127.0.0.1:12999`.
5. `archipelago.py` se connecte au WebSocket, envoie la whitelist des flags à surveiller, puis écoute les événements.
6. Quand un flag surveillé est activé (boss tué, item ramassé…), le DLL le forwarde au client Python.
7. Le client Python peut envoyer des items à donner via le WebSocket ou l'endpoint HTTP `/give`.

---

## Build

### Prérequis

- **MinGW64** cross-compilateur (`x86_64-w64-mingw32-g++`)
- `mingw-w64`

### Compilation

```bash
./mingw.sh
```

Génère `myserver.dll`.

### Injection

Injecter `myserver.dll` dans le processus `eldenring.exe` (avec n'importe quel injecteur DLL).

---

## Utilisation

1. Lancer Elden Ring.
2. Injecter `myserver.dll`.
3. Lancer le client Python :
   ```bash
   python3 Archipelago_ws_py/archipelago.py
   ```
4. Le client se connecte au DLL, envoie la whitelist des flags, et commence à monitorer.

### API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/test` | Vérifier que le serveur tourne |
| GET | `/give?base_id=X&type=Y&qty=Z&upgrade=W&ash=A` | Donner un item |
| WS | `/ws` | WebSocket pour recevoir les flags et donner des items |

---

## Contribuer

**Si tu veux contribuer**, lis d'abord le code source du projet pour comprendre comment les hooks, l'AOB scanning et le serveur fonctionnent.

Les AOB patterns sont définis dans :
- `game.cpp` — patterns pour `AddItem` et `InventoryAccessor`
- `flag.cpp` — pattern pour `EventFlagFunc`

Si tu es sur une version différente d'Elden Ring, ces patterns ne matcheront probablement pas. Tu devras trouver les nouveaux AOB avec un outil comme Cheat Engine (ou t'inspirer des CT de HeXinton).

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `main.cpp` | Point d'entrée DLL (`DllMain`) |
| `server.cpp` | Serveur HTTP/WS (port 12999) |
| `game.cpp` | Patterns AOB + résolution des fonctions |
| `hook.cpp` | Hook sur `AddItem` + système d'appel |
| `flag.cpp` | Hook sur `SetEventFlag` + file d'événements |
| `aob_scanner.cpp` | Scanner AOB générique avec wildcards |
| `types.h` | Structures `ItemData`, `ItemType` |
| `Archipelago_ws_py/archipelago.py` | Client Python de connexion |
| `Archipelago_ws_py/map_items.json` | Mapping flags → items |
| `mingw.sh` | Script de compilation