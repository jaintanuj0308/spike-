# Frontend & Central Backend Integration Guide

This guide details the APIs, WebSockets, and payloads required to integrate your custom UI dashboard (frontend) and main database/match server (central backend) with the Raspberry Pi Spike System.

---

## 1. REST API Specification

Your central backend or supervisor screens can send HTTP requests directly to the Pi's server at: `http://<pi-ip>:8001`

| Endpoint | Method | Payload | Description |
| :--- | :--- | :--- | :--- |
| `/status` | `GET` | *None* | Returns the complete current state of the Spike as JSON. |
| `/reset` | `POST` | *None* | Resets the game state back to `idle`, stopping any active timers. |
| `/kill/{player_id}` | `POST` | *None* | Simulates a player death event (simulates pulling the key for `player_id`). |
| `/plant/{player_id}`| `POST` | *None* | Manually triggers the plant start sequence (Attacker `player_id`). |
| `/defuse/{player_id}`| `POST` | *None* | Manually triggers the defusal start sequence (Defender `player_id`). |

#### Sample `/status` Response Payload:
```json
{
  "state": "planted",
  "plant_remaining": 0,
  "spike_remaining": 34,
  "defuse_remaining": 60,
  "planter_id": "A1",
  "defuser_id": null
}
```

---

## 2. WebSocket Real-Time Channel

Open a connection to: `ws://<pi-ip>:8001/ws`

### Server-to-Client Broadcasts
Every time a countdown ticks, a state changes, or a USB is inserted/pulled, the Pi broadcasts the updated state payload to **all connected clients**:

```json
{
  "event": "state_update",
  "state": "defusing",
  "plant_remaining": 0,
  "spike_remaining": 28,
  "defuse_remaining": 48,
  "planter_id": "A1",
  "defuser_id": "D1"
}
```

### Client-to-Server Commands
Umpire screens or dashboards can push actions to the Pi by sending JSON packets through the socket:

*   **Force Explode Spike:**
    ```json
    { "event": "force_explode" }
    ```
*   **Trigger Player Killed/Key Pull:**
    ```json
    { "event": "player_killed", "player_id": "D1" }
    ```
*   **Reset Round:**
    ```json
    { "event": "reset_round" }
    ```

---

## 3. Frontend Integration Code (React Hook)

Use this complete custom React hook (`useSpikeState.js`) to bind the game state to your components:

```javascript
import { useState, useEffect, useRef } from "react";

export function useSpikeState(piIP = "192.168.1.100") {
  const [spikeState, setSpikeState] = useState(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    function connect() {
      console.log("Connecting to Spike WebSocket...");
      const ws = new WebSocket(`ws://${piIP}:8001/ws`);

      ws.onopen = () => {
        setConnected(true);
        console.log("Connected to Spike!");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event === "state_update" || !data.event) {
          setSpikeState(data);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        console.log("Spike connection closed. Reconnecting in 3s...");
        setTimeout(connect, 3000); // Auto-reconnection logic
      };

      ws.onerror = (err) => {
        console.error("Spike Socket Error: ", err);
        ws.close();
      };

      socketRef.current = ws;
    }

    connect();

    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, [piIP]);

  // Methods to trigger overrides
  const sendCommand = (eventPayload) => {
    if (socketRef.current && connected) {
      socketRef.current.send(JSON.stringify(eventPayload));
    }
  };

  return { spikeState, connected, sendCommand };
}
```

---

## 4. Central Backend Integration Code (Node.js)

Connect your central game server to the Pi to persist match outcomes to a SQL/NoSQL database:

```javascript
const WebSocket = require('ws');

const PI_WS_URL = 'ws://192.168.1.100:8001/ws';
let ws;

function connectToSpike() {
  ws = new WebSocket(PI_WS_URL);

  ws.on('open', () => {
    console.log('Connected to Spike Game hardware');
  });

  ws.on('message', async (data) => {
    const state = JSON.parse(data);
    
    // Detect final match conditions
    if (state.state === 'exploded') {
      console.log(' Detonation detected. Recording Attacker victory.');
      await saveMatchResults({ winner: 'attackers', remainingDefuse: state.defuse_remaining });
    } else if (state.state === 'defused') {
      console.log(' Defusal detected. Recording Defender victory.');
      await saveMatchResults({ winner: 'defenders', remainingSpike: state.spike_remaining });
    }
  });

  ws.on('close', () => {
    console.warn('Spike hardware disconnected. Re-trying in 5 seconds...');
    setTimeout(connectToSpike, 5000);
  });

  ws.on('error', (err) => {
    console.error('Spike socket error:', err.message);
    ws.close();
  });
}

async function saveMatchResults(outcome) {
  // Call your database or central API here
  console.log('Saving to DB:', outcome);
}

connectToSpike();
```
