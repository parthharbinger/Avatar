# AI Avatar Platform — Simple End-to-End Execution Flow

> **Summary:** A crisp, step-by-step guide showing exactly **which folder, which file, and which function** is called at every step from **User Input (Voice/Text) to Final Output (Avatar Video & Speech)**.

---

## 🚀 30-Second Linear Flow Diagram

```
[ STEP 1: INPUT ] ──────► [ STEP 2: TURN CONTROL ] ───► [ STEP 3: RAG SEARCH ] ───► [ STEP 4: LLM BRAIN ]
User speaks or types      Handles state & barge-in      Searches uploaded docs        Generates answer text
                                                                                            │
                                ┌───────────────────────────────────────────────────────────┘
                                ▼
                   [ STEP 5: OUTPUT GENERATION ]
                   Choose either Engine A or Engine B:
                   ├──► ENGINE A: 2D Neural Canvas (Edge-TTS + 60 FPS Canvas)
                   └──► ENGINE B: Live WebRTC Video (D-ID / Simli Stream)
```

---

## 📍 Step-by-Step Execution Flow

---

### Step 1: User Input (Voice or Text)
The user either speaks into the microphone or types a question in the chat box.

* **What happens:** 
  * If speaking, browser captures voice audio and turns it into text instantly.
  * If typing, the text string is captured from the input field.
* **Folder:** `sdk/src/` or `demo/`
* **File:** [`sdk/src/widget.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/widget.ts) (or [`demo/index.html`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/demo/index.html))
* **Function Called:**
  * `_setupSpeechRecognition()` &rarr; listens to browser microphone (`webkitSpeechRecognition`).
  * `recognition.onresult(event)` &rarr; extracts text transcript.
* **Data Flow:**
  * **Input:** User voice audio from microphone.
  * **Output:** String text (e.g., `"What is your return policy?"`).

---

### Step 2: Turn Orchestration & Barge-In Check
Checks if the avatar is already speaking. If the user interrupts, it stops the avatar immediately.

* **What happens:** 
  * If avatar is currently talking and user speaks (>2 characters), it aborts previous playback.
  * Prepares request payload with conversation history.
* **Folder:** `sdk/src/` or `demo/`
* **File:** [`sdk/src/widget.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/widget.ts) (or [`demo/index.html`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/demo/index.html))
* **Function Called:**
  * `_executeConversationalTurn(userQuery)` &rarr; main turn controller.
  * `_triggerBargeIn()` &rarr; (if interrupted) calls `askAbortController.abort()` and `audio.stop()`.
* **Data Flow:**
  * **Input:** Question text (`userQuery`).
  * **Output:** Dispatches HTTP POST request to backend.

---

### Step 3: RAG Knowledge Retrieval (Uploaded Documents)
If a custom expert profile is selected, searches uploaded PDFs/DOCs for the exact answer.

* **What happens:** 
  * Tokenizes user query and calculates BM25 keyword relevance scores across all indexed document chunks in under 5 milliseconds.
* **Folder:** `app/services/`
* **File:** [`app/services/rag_service.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/services/rag_service.py)
* **Functions Called:**
  1. `retrieve_context_with_sources(profile_id, query)` &rarr; main RAG query function.
  2. `_bm25_score(query_tokens, chunk_text)` &rarr; mathematical relevance ranking.
* **Data Flow:**
  * **Input:** `profile_id` + User Question (`query`).
  * **Output:** Top matching document text passages + citation source metadata (`filename`, `score`, `snippet`).

---

### Step 4: AI Thinking & Answer Generation (LLM)
Sends the user question + document knowledge to Groq LLM (LLaMA 3.3) for an intelligent answer.

* **What happens:** 
  * Builds a grounded system prompt and gets an answer in <150ms.
* **Folder:** `app/api/`
* **File:** [`app/api/conversation.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/conversation.py)
* **Function Called:**
  * `generate_response(body: ChatRequest)` &rarr; FastAPI route `POST /api/v1/chat/respond`.
* **Data Flow:**
  * **Input:** `{ "message": "...", "history": [...], "profile_id": "..." }`.
  * **Output:** `{ "reply": "Items can be returned within 30 days.", "sources": [...] }`.

---

## 🎬 Step 5: Output Generation (2 Engine Options)

The generated answer text is rendered to the user via **Engine A** or **Engine B**:

---

### 👉 Path A: 2D Neural Canvas (Zero-GPU, Edge-TTS)

#### 5A.1 Voice Generation & Boundary Timing
* **Folder:** `app/tts/`
* **File:** [`app/tts/edge_tts_adapter.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/tts/edge_tts_adapter.py)
* **Function Called:** `EdgeTTSAdapter.stream_speech_with_boundaries(text, voice)`
* **What it does:** Synthesizes MP3 voice chunks and extracts exact millisecond `WordBoundary` timestamps.

#### 5A.2 Viseme Lip-Sync Mapping
* **Folder:** `app/viseme/`
* **File:** [`app/viseme/mapper.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/viseme/mapper.py)
* **Function Called:** `from_word_boundaries(word_boundaries)`
* **What it does:** Converts words/letters into mouth shape keyframes (`open`, `round`, `dental`, `bilabial`, `neutral`).

#### 5A.3 WebSocket Transmission
* **Folder:** `app/orchestration/` & `app/api/`
* **Files:** [`app/orchestration/pipeline.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/orchestration/pipeline.py) & [`app/api/websocket.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/websocket.py)
* **Function Called:** `run_speech_pipeline(websocket, text, voice)`
* **What it does:** Streams `viseme_timeline` JSON and Base64 `audio_chunk` packets over WebSocket.

#### 5A.4 Browser Playback & 60 FPS Drawing
* **Folder:** `sdk/src/`
* **Files:** [`sdk/src/audio.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/audio.ts) & [`sdk/src/renderer2d.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/renderer2d.ts)
* **Functions Called:**
  * `SeamlessAudioEngine.enqueue(base64)` &rarr; decodes and plays WebAudio gaplessly.
  * `Renderer2D.render(elapsedMs)` &rarr; draws 60 FPS eye blinking, Cupid's bow, oral cavity, and teeth on `<canvas>`.
* **Output:** Synchronized natural voice and animated digital human face.

---

### 👉 Path B: Live WebRTC Digital Human (Photorealistic Video)

#### 5B.1 WebRTC Handshake (SDP & ICE)
* **Folder:** `app/api/` & `app/avatar_providers/`
* **Files:** [`app/api/sessions.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/sessions.py) & [`app/avatar_providers/did_adapter.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/avatar_providers/did_adapter.py) (or `simli_adapter.py`)
* **Functions Called:**
  * `create_webrtc_offer()` &rarr; gets SDP Offer from provider cloud.
  * `submit_webrtc_answer()` &rarr; sends client SDP Answer to provider.
  * `submit_webrtc_ice()` &rarr; connects P2P WebRTC connection.

#### 5B.2 Trigger Live Speech & Video Stream
* **Folder:** `app/api/` & `app/avatar_providers/`
* **Files:** [`app/api/sessions.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/sessions.py) & [`app/avatar_providers/did_adapter.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/avatar_providers/did_adapter.py)
* **Function Called:** `webrtc_speak()` &rarr; `DIDAvatarProvider.speak(stream_id, text)`
* **What it does:** Sends answer text to D-ID/Simli cloud API. Provider renders neural lip-synced video frames into the WebRTC stream.

#### 5B.3 Video Playback
* **Folder:** `demo/` or `sdk/src/`
* **File:** [`demo/index.html`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/demo/index.html)
* **Element:** `<video id="avatar-video">` (receives WebRTC `MediaStream` track).
* **Output:** Photorealistic live video of the avatar speaking.

---

## 📊 Complete Master Reference Table

| Step | What Happens | Folder | File | Function Called | Input &rarr; Output |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | **User Speaks / Types** | `sdk/src/` | [`widget.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/widget.ts) | `_setupSpeechRecognition()` | Voice audio &rarr; Text string |
| **2** | **Orchestrate Turn / Barge-In** | `sdk/src/` | [`widget.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/widget.ts) | `_executeConversationalTurn()` | Text string &rarr; Dispatches chat request |
| **3** | **Search Documents (RAG)** | `app/services/` | [`rag_service.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/services/rag_service.py) | `retrieve_context_with_sources()` | Question &rarr; Relevant text passages |
| **4** | **Generate Answer (LLM)** | `app/api/` | [`conversation.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/conversation.py) | `generate_response()` | Question + Context &rarr; Answer text |
| **5A** | **Voice Synthesis (Edge-TTS)** | `app/tts/` | [`edge_tts_adapter.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/tts/edge_tts_adapter.py) | `stream_speech_with_boundaries()` | Answer text &rarr; MP3 chunks + Timestamps |
| **5A** | **Lip-Sync Visemes** | `app/viseme/` | [`mapper.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/viseme/mapper.py) | `from_word_boundaries()` | Timestamps &rarr; Mouth shape timeline |
| **5A** | **Stream Chunks (WS)** | `app/orchestration/`| [`pipeline.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/orchestration/pipeline.py) | `run_speech_pipeline()` | Pipeline task &rarr; WebSocket messages |
| **5A** | **Draw 60 FPS Canvas** | `sdk/src/` | [`renderer2d.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/renderer2d.ts) | `Renderer2D.render()` | Visemes &rarr; 60 FPS Canvas drawing |
| **5B** | **Live WebRTC Video** | `app/avatar_providers/`| [`did_adapter.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/avatar_providers/did_adapter.py) | `DIDAvatarProvider.speak()` | Answer text &rarr; Live WebRTC video stream |
