# Presenter Guide — A2A Protocol Slide Decks

Reference this document on your second monitor while presenting.
Each section covers one slide with talking points you can speak to naturally.

---

# PART 1 — A2A_Protocol_Concepts.pptx (20 slides)

*Audience: Developers and architects seeing A2A for the first time.*

---

## Slide 1 — Title: Agent2Agent (A2A) Protocol

**What's on screen:** Title, tagline, "Google → Linux Foundation", year 2026.

**What to say:**
> Welcome. Today we're going to explore the Agent2Agent protocol — A2A for short. A2A is an open standard that gives AI agents a common language, so any agent built on any framework can talk to any other agent without custom glue code. It was originally created by Google, but it's now governed by the Linux Foundation, which means no single company controls its direction. By the end of this session you'll understand what A2A is, how it works, and how to use it in your own systems.

---

## Slide 2 — Agenda

**What's on screen:** Numbered list of 18 topics.

**What to say:**
> Here's our roadmap. We'll start with the problem A2A solves, then build up from the basic concepts — what an agent card is, how tasks work, what a message looks like — and then cover the more advanced features like streaming, authentication, and multi-turn interactions. By slide 17 we'll have a clear picture of the full protocol, and slide 18 points you to where to go next.

---

## Slide 3 — The Problem: Before A2A

**What's on screen:** Two panels — red "Before A2A" and green "With A2A".

**What to say:**
> Before A2A existed, integrating AI agents was painful. Developers had two options: wrap one agent as a tool inside another, which stripped away the agent's native negotiation ability; or write custom point-to-point integration code for every pair of agents. If you had five agents, that's potentially 10 custom integrations. Add a sixth agent and you need five more. The engineering overhead grows as O(n²). There was no shared security model, so every integration handled auth differently, creating gaps.

> A real example: imagine building a trip-planning system. You need a flight agent, a hotel agent, a currency agent, and a tour agent. Without A2A, you're writing custom glue between each of them. With A2A, every agent speaks the same protocol. Any compliant agent works with any other — the integration surface is always one standard interface.

---

## Slide 4 — What is A2A?

**What's on screen:** Four cards: What / Origin / Purpose / Scope.

**What to say:**
> A2A is an open protocol standard for AI agent-to-agent communication. It defines how agents discover each other, authenticate, and exchange tasks and messages. Think of it as HTTP for agents — a well-known, universally understood interface.

> It was created at Google and is now under the Linux Foundation's open governance, which ensures it evolves in a vendor-neutral way.

> The scope is specifically agent-to-agent. It's a companion to MCP — the Model Context Protocol — which handles agent-to-tool communication. If MCP is how your agent talks to a database or an API, A2A is how your agent talks to another agent. The two protocols work together to cover the full integration stack.

---

## Slide 5 — A2A in the AI Stack

**What's on screen:** Three-layer diagram: MCP at the bottom, A2A in the middle, Frameworks at the top.

**What to say:**
> Think of the AI stack as three layers. At the bottom, MCP connects AI models to tools and data sources — databases, file systems, external APIs. In the middle, A2A enables agents to communicate with other agents — delegating tasks, multi-turn reasoning, negotiation. At the top, frameworks like Google ADK, LangChain, CrewAI, Semantic Kernel, and AutoGen are used to build the actual agents.

> A2A sits at that critical middle layer. It's the reason you can build an ADK agent and have it talk to a LangChain agent without any custom translation layer. The two agents both speak A2A, so they just work together.

---

## Slide 6 — Key Design Principles

**What's on screen:** Five vertical columns — Simplicity, Enterprise Readiness, Async Operations, Modality Independence, Opaque Execution.

**What to say:**
> A2A was designed around five principles, and each one was a deliberate choice.

> **Simplicity** — A2A uses HTTP, JSON-RPC 2.0, and Server-Sent Events. These are technologies every web developer already knows. The protocol doesn't invent new transport mechanisms.

> **Enterprise Readiness** — This wasn't an afterthought. Authentication, authorization, security, privacy, distributed tracing, and monitoring are all specified in the protocol from day one. You can run A2A in production without bolting on security later.

> **Async Operations** — Many real agent tasks take a long time. A2A has first-class support for long-running tasks, incremental streaming, push notifications, and human-in-the-loop workflows.

> **Modality Independence** — Agents don't just exchange text. A2A supports plain text, files (images, PDFs, binaries), and structured JSON data — anything with a MIME type.

> **Opaque Execution** — Agents collaborate without revealing their internal logic, model, or proprietary tools. The server is a black box to the client. This protects intellectual property and implementation secrets.

---

## Slide 7 — Core Actors

**What's on screen:** Three boxes connected by arrows: User → A2A Client → A2A Server.

**What to say:**
> Every A2A interaction involves three actors.

> The **User** is whoever or whatever is initiating the request — a human, an automated pipeline, or even another system. They have a goal they want accomplished.

> The **A2A Client** — also called the Client Agent — acts on the user's behalf. It could be an application, a service, or another AI agent. The client is responsible for initiating communication, sending tasks, managing authentication, and handling the response — whether that's polling for results or consuming a streaming SSE connection.

> The **A2A Server** — the Remote Agent — is an AI agent that exposes an HTTP endpoint implementing the A2A specification. It receives tasks, processes them, and returns messages and artifacts. From the client's perspective, the server is completely opaque. You don't know what model it's using, what tools it has, or how it works internally. You only see what it produces.

---

## Slide 8 — Fundamental Concepts

**What's on screen:** Five cards: Agent Card, Task, Message, Part, Artifact.

**What to say:**
> Five concepts form the core vocabulary of A2A. Once you understand these, everything else falls into place.

> **Agent Card** — A JSON document that describes an agent: who it is, what it can do, how to authenticate, and where to send requests. It's the discovery mechanism.

> **Task** — The stateful unit of work. Every interaction with an agent creates or resumes a Task. Tasks have unique IDs, they live through a defined lifecycle of states, and they persist on the server so you can poll or stream updates.

> **Message** — A single communication turn. It has a role — either "user" or "agent" — and contains one or more Parts. Messages are how instructions, context, and answers flow between client and server.

> **Part** — The smallest content unit. A Part can be a TextPart (plain text), a FilePart (a file by URL or raw bytes), or a DataPart (structured JSON). Parts are always typed with a MIME type.

> **Artifact** — The tangible output an agent produces. Think of it as the deliverable: a document, an image, a structured JSON result. Artifacts are composed of Parts and are returned as part of a completed Task.

---

## Slide 9 — Agent Card Deep Dive

**What's on screen:** Description on the left, example JSON on the right.

**What to say:**
> The Agent Card is the foundation of agent discovery. Every A2A agent serves this JSON document at a well-known URL: `/.well-known/agent.json`. Any client can fetch that URL and immediately know everything they need to connect.

> The card contains five key pieces of information: **Identity** — name, description, version. **Capabilities** — does the agent support streaming? Push notifications? **Skills** — specific tasks the agent can perform, with descriptions the client's LLM can read and reason about. **Authentication** — what schemes are required (Bearer token, API Key, OAuth2, etc.). **Endpoint URL** — where to send requests.

> There's also an **Extended Agent Card** concept — after a client authenticates, they can fetch additional private capabilities that aren't advertised publicly. This is useful for tiered access models where premium features are only visible to authenticated clients.

> The JSON you see here is a minimal example. In practice, a skill entry would also include `inputModes`, `outputModes`, `tags`, and `examples` to help the orchestrator route requests to the right agent.

---

## Slide 10 — The Task Lifecycle

**What's on screen:** State diagram with 6 state boxes and connecting arrows, plus a legend at the bottom.

**What to say:**
> Every A2A interaction flows through this state machine. Let's walk through it.

> When you call `tasks/send`, the task is immediately in **submitted** state — the server has received it but hasn't started processing it yet.

> The agent picks it up and transitions to **working**. This is where the actual processing happens. If the agent supports streaming, it will emit incremental artifact chunks during this phase.

> From **working**, there are four possible exits. **Completed** means success — artifacts are ready. **Failed** is a terminal error — you can read the error details in the task response. **Canceled** means the client called `tasks/cancel` — also terminal.

> The fourth exit is **input-required**. This is the multi-turn mechanism. The agent pauses, puts a question in `status.message`, and waits. The client reads the question, gets an answer, and resumes the *same task* by calling `tasks/send` again with the same task ID. The task then goes back to **working**.

> This state machine is what makes A2A suitable for complex, real-world agent workflows — not just simple one-shot requests.

---

## Slide 11 — Messages & Parts

**What's on screen:** Message structure fields at top, four Part/Artifact type cards below.

**What to say:**
> Let's look at the wire format. A **Message** has four key fields: a `messageId` for idempotency, a `taskId` linking it to its parent task, a `role` (either "user" or "agent"), and a list of `parts` which is where the actual content lives.

> **TextPart** is the simplest — it carries plain text with kind "text". This is what you use for instructions, questions, and narrative responses.

> **FilePart** carries files. There are two variants: by URL (great for large files hosted on S3 or GCS — you just pass the URL and MIME type), or by raw bytes (base64-encoded, for smaller inline files like images or short PDFs). The MIME type tells the receiving agent how to interpret the content.

> **DataPart** carries structured JSON. This is the machine-readable format — when an agent returns hotel search results or a booking confirmation, it comes as a DataPart so the orchestrator can parse and forward it programmatically.

> **Artifacts** are the agent's deliverables. An artifact has a name, an index (for multi-part artifacts), a `lastChunk` flag (for streaming), and a list of Parts. The artifact is what ends up in the task's result after completion.

---

## Slide 12 — Interaction Patterns

**What's on screen:** Three columns — Request/Response Polling, Streaming SSE, Push Notifications.

**What to say:**
> A2A gives you three patterns for receiving updates from a server, and you choose based on your use case.

> **Request/Response with Polling** is the simplest. You send a message, get back a Task in "working" state, then periodically call `tasks/get` until it reaches a terminal state. Low complexity, but higher latency for long-running tasks. Good for tasks that complete quickly or where you check results later.

> **Streaming with Server-Sent Events** is the real-time pattern. You call `tasks/sendSubscribe` and keep an HTTP connection open. The server pushes events to you as they happen — task state changes and incremental artifact chunks. You see results as they stream in, just like a streaming LLM response. This is ideal for generative tasks where the user expects live output.

> **Push Notifications** are for very long-running tasks — minutes, hours — where maintaining a connection isn't practical. You register a webhook URL on the server before starting the task. The server POSTs the full task result to your webhook when it completes. Your client is completely free to do other work in the meantime. This pattern fits batch processing, price monitoring, document generation pipelines, and any serverless architecture.

---

## Slide 13 — The 11 Core Operations

**What's on screen:** Table of all 11 operations grouped by category.

**What to say:**
> The entire A2A API surface is exactly 11 operations, organized into four categories.

> **Messaging** — two operations: `Send Message` for synchronous requests and `Send Streaming Message` for SSE-streamed responses. These are the workhorses you'll use in almost every interaction.

> **Task Management** — four operations: `Get Task` for polling current state, `List Tasks` to query your task history with filters, `Cancel Task` to stop an in-progress task, and `Subscribe to Task` to open a streaming connection to a task you already created.

> **Push Notifications** — four operations to manage webhooks: create, get, list, and delete. Each task can have its own webhook configuration.

> **Discovery** — one operation: `Get Extended Agent Card`, which retrieves the full capability set after authentication.

> One important protocol guarantee: `Get Task` and `Cancel Task` are **idempotent** — you can call them multiple times safely. `Send Message` *may* be idempotent if you reuse the same `messageId`, which is useful for retry-safe clients.

---

## Slide 14 — Protocol Bindings

**What's on screen:** Three columns — JSON-RPC 2.0, gRPC, HTTP+JSON/REST — each with code snippets.

**What to say:**
> A2A is binding-agnostic. The same operations can be expressed over three different transports.

> **JSON-RPC 2.0** is the primary binding used by all official SDKs. It wraps operations in a standard JSON-RPC 2.0 envelope with a `method` field like `"tasks/send"`. Easy to debug with standard HTTP tools like curl or Postman, and works over any HTTP/1.1 or HTTP/2 connection.

> **gRPC** is for high-performance scenarios. It uses Protocol Buffers for binary encoding, runs over HTTP/2 with multiplexing, and provides strongly-typed auto-generated client stubs. Best suited for microservice architectures where latency and throughput matter.

> **HTTP+JSON/REST** is the most familiar format for web developers. Standard HTTP verbs with JSON bodies. It's compatible with OpenAPI/Swagger tooling and drops straight into existing API gateways.

> For most use cases, you'll use JSON-RPC 2.0 via the official SDK. But if you need to integrate into a gRPC-first microservice mesh, that binding is available without any compromise to the protocol semantics.

---

## Slide 15 — Authentication & Security

**What's on screen:** Five auth scheme cards and a four-step "how it works" strip.

**What to say:**
> A2A supports five authentication schemes to cover the full range of enterprise requirements.

> **API Key** — the simplest option. A secret key passed in an HTTP header on every request. Fast to implement, good for service-to-service. Rotate keys regularly.

> **HTTP Bearer Token** — `Authorization: Bearer <token>`. Works with JWT or opaque tokens. Very widely supported. Always use over TLS.

> **OAuth 2.0** — the full OAuth flow with three grant types: Authorization Code for user-facing apps, Client Credentials for machine-to-machine, and Device Code for headless devices. Tokens are short-lived, which limits exposure if a token is compromised.

> **OpenID Connect** — OAuth 2.0 with an identity layer. Adds a signed JWT ID token with user claims. Used in the standard A2A request lifecycle for authenticated discovery.

> **Mutual TLS** — the strongest option. Both client and server present certificates. This is the zero-trust model used in regulated industries like finance and healthcare.

> The flow is: the client fetches the Agent Card, reads which scheme is required, obtains the appropriate credential, then passes it as an HTTP header on every single request. The server validates the credential before processing any task.

---

## Slide 16 — Multi-Turn Interactions

**What's on screen:** Definitions of contextId, taskId, referenceTaskIds, input-required. Conversation flow diagram on the right.

**What to say:**
> Real agent conversations don't happen in a single request-response cycle. A2A has first-class support for multi-turn interactions.

> **contextId** is the key concept here. It's a server-generated identifier that groups all related tasks and messages under one logical conversation. When you send a follow-up message, you include the same contextId, and the server knows this is part of the same conversation thread.

> **taskId** identifies each individual unit of work. You use it to poll, stream, cancel, or resume a specific task.

> **referenceTaskIds** lets a message explicitly reference one or more previous tasks. This is how you build dependency chains — "here's the result of the flight search, now use it to suggest hotels."

> The **input-required** state, which we covered in the lifecycle slide, is the mechanism for back-and-forth within a single task. The conversation flow on the right shows a simple example: the client asks to plan a Paris trip, the server returns `input-required` asking for dates and budget, the client answers with the same contextId, and the server completes the task with a full itinerary.

---

## Slide 17 — Request Lifecycle

**What's on screen:** Four numbered stage columns with code boxes.

**What to say:**
> Let's put it all together into the full request lifecycle.

> **Stage 1 — Discovery.** The client does a GET to `/.well-known/agent.json`. The response is the Agent Card. From this, the client knows the agent's capabilities, endpoint URL, and what authentication it needs.

> **Stage 2 — Authentication.** The client reads the auth scheme from the card and obtains credentials. If OpenID Connect is required, it exchanges for a JWT. If API Key, it reads from config. The credential is ready to inject into every subsequent request.

> **Stage 3 — sendMessage.** The client sends a JSON-RPC 2.0 request to the agent's endpoint with method `tasks/send`. The server returns a Task object. If the task completes quickly, it might already be in "completed" state. Otherwise it will be in "working".

> **Stage 4 — sendMessageStream.** For tasks that take longer, or when the agent supports streaming, the client opens an SSE connection with `tasks/sendSubscribe`. The server pushes `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` messages down the stream until the task reaches a terminal state.

---

## Slide 18 — SDK & Framework Support

**What's on screen:** Five SDK tiles, six framework cards.

**What to say:**
> A2A has official, open-source SDKs for the five most common languages: Python, JavaScript, Java, C#/.NET, and Go. All are on GitHub under the `google-a2a` organization and published under the Apache 2.0 license.

> On the framework side, Google's own ADK — the Agent Development Kit — has first-class A2A support with built-in server and client classes. But A2A is designed to be framework-agnostic: LangChain, CrewAI, Semantic Kernel, and AutoGen all integrate with A2A, meaning you can build a mixed-framework agent network where each agent uses the best tool for its job.

> And if none of these fit, you can build A2A support into any custom platform. All you need is an HTTP server, the ability to serve JSON, and the willingness to implement the 11 operations. The spec is completely open.

---

## Slide 19 — Key Takeaways

**What's on screen:** Six numbered takeaway cards in a 2×3 grid.

**What to say:**
> Six things to remember.

> **One** — A2A is an open standard governed by the Linux Foundation. It's not a proprietary lock-in play.

> **Two** — A2A treats agents as first-class citizens, not tools. This preserves their multi-turn reasoning, negotiation, and long-running task capabilities.

> **Three** — Enterprise readiness is built in from day one. OAuth, mTLS, tracing, monitoring — you don't have to bolt these on later.

> **Four** — A2A and MCP are complementary, not competing. Together they form a complete AI integration stack: MCP for tools and data, A2A for agent-to-agent collaboration.

> **Five** — The adoption cost is low. HTTP, JSON-RPC, and SSE are things developers already know. The protocol doesn't invent new concepts unnecessarily.

> **Six** — As AI systems become more complex, standardized agent communication becomes essential. A2A is the foundation for the multi-agent AI systems that will power the next generation of applications.

---

## Slide 20 — Resources

**What's on screen:** Four resource cards — official site, Linux Foundation, SDKs, DeepLearning.AI course.

**What to say:**
> To dive deeper: the full specification and topic guides are at `a2a-protocol.org`. Official SDKs are at `github.com/google-a2a`. The Python SDK installs with a single `pip install a2a-sdk`.

> If you prefer structured learning, DeepLearning.AI has a free short course on building agents with A2A and the Google ADK — hands-on coding labs included.

> And with that, we've covered the full A2A protocol from first principles. Any questions before we move on to the tutorial project?

---
---

# PART 2 — A2A_Tutorial.pptx (31 slides)

*Audience: Developers building the Travel Planning Multi-Agent System tutorial.*

---

## Slide 1 — Title: A2A Protocol Tutorial

**What's on screen:** Title, subtitle "Travel Planning Multi-Agent System", date.

**What to say:**
> This deck walks through the hands-on tutorial. We're going to build a complete multi-agent travel planning system that exercises every single feature of the A2A protocol in a realistic scenario. By the end you'll have seen — and built — agent cards, tasks, streaming, multimodal content, input-required flows, push notifications, auth, error handling, and multi-agent orchestration. All in one cohesive project.

---

## Slide 2 — Table of Contents

**What's on screen:** 12 section list.

**What to say:**
> We have 12 sections. The first section covers the "why" of A2A, and each subsequent section introduces a new protocol feature and builds it into the project. Sections 1–11 each teach a concept, and Section 12 wires everything together into a running system.

---

## Slide 3 — Project Architecture

**What's on screen:** Diagram showing User → Travel Orchestrator → 4 specialist agents.

**What to say:**
> Our project is a Travel Planning Multi-Agent System. At the top, the user sends a natural-language travel request. The **Travel Orchestrator** — an ADK LlmAgent — receives it and coordinates four specialist agents.

> The **Flight Agent** handles flight search. It supports SSE streaming and uses Bearer token authentication.

> The **Hotel Agent** handles hotel search. It accepts PDF brochures as multimodal input and uses API key authentication.

> The **Booking Agent** handles ticket booking. It uses the input-required multi-turn flow and supports push notifications for async confirmation.

> The **Weather Agent** provides weather forecasts via SSE streaming.

> Each agent runs as its own FastAPI server. Together they demonstrate every A2A protocol feature in a realistic context.

---

## Slide 4 — Section 1: What Is A2A and Why Does It Matter

**What's on screen:** The interoperability problem and A2A solution.

**What to say:**
> Before A2A, every multi-agent system required custom glue code. If you had four agents — flight, hotel, weather, booking — you needed custom integration between each pair. Adding a fifth agent meant writing four more custom connections.

> A2A solves this with an open HTTP-based standard. Any compliant agent, regardless of framework — ADK, LangChain, CrewAI, AutoGen — can communicate with any other. The integration cost drops from O(n²) to O(1): one standard interface for every agent.

> ADK implements A2A through two classes: `A2AServer` (which wraps your agent logic and serves the protocol endpoints) and `A2AClient` (which lets any agent send tasks to any A2A-compliant endpoint). In our tutorial, the orchestrator uses `A2AClient` as a tool to talk to all four specialist agents.

---

## Slide 5 — Section 1: Core Architecture

**What's on screen:** JSON-RPC wire format and endpoint list.

**What to say:**
> Under the hood, A2A is JSON-RPC 2.0 over HTTP. Every request is a POST with a JSON body containing a `method` field — for example `tasks/send`, `tasks/get`, or `tasks/cancel`.

> The key endpoints are: `tasks/send` to create or resume a task, `tasks/sendSubscribe` for SSE streaming, `tasks/get` to poll state, `tasks/cancel` to stop a task, and `tasks/pushNotification/set` to register a webhook.

> These endpoints are served automatically by the `A2AStarletteApplication` class from the ADK SDK — you implement your logic in an `AgentExecutor` and the framework handles all the protocol plumbing.

---

## Slide 6 — Section 2: Agent Cards — Flight Agent Example

**What's on screen:** Agent Card JSON for the Flight Agent.

**What to say:**
> Every A2A agent serves a machine-readable JSON document at `/.well-known/agent.json`. This is the Agent Card — the agent's identity and capability advertisement.

> The Flight Agent's card declares: its name and URL on port 8001, `streaming: true` (it supports SSE), `stateTransitionHistory: true` (it keeps a log of state changes), and Bearer token authentication under the `authentication` key.

> The `skills` array lists what this agent can do. Each skill has an `id`, a `name` the LLM can read, `inputModes` (what MIME types it accepts), `outputModes` (what it returns), and `examples` to help an orchestrator understand when to route to this agent.

> A client fetches this card before sending any task, reads what auth is needed, and injects the right credentials. The ADK generates this card automatically from your configuration — you don't write JSON by hand.

---

## Slide 7 — Section 2: Agent Cards — Hotel & Booking Examples

**What's on screen:** Hotel and Booking Agent card details, auth scheme table.

**What to say:**
> The Hotel Agent uses API Key authentication — clients must pass an `X-Api-Key` header. Its skill declares `inputModes: ["application/pdf", "text/plain"]` because it can accept PDF brochures in addition to text queries. The `outputModes` include `application/json` for structured hotel results.

> The Booking Agent declares `pushNotifications: true` in its capabilities, which signals to clients that they can register a webhook before submitting a task.

> The table on the right summarizes every Agent Card field we demonstrate in the tutorial — from basic identity fields all the way to capability flags and auth schemes. Notice how the card is the single source of truth: by reading it, a client has everything it needs to interact with the agent correctly.

---

## Slide 8 — Section 3: Tasks — Data Model

**What's on screen:** TaskSendParams, Message, Part types, Task response, Artifact structure.

**What to say:**
> Every A2A interaction is a Task. When you create a task, you build a `TaskSendParams` object with three key fields: `id` — a client-generated UUID, `message` — the initial user message, and optionally `sessionId` — to group related tasks under a conversation.

> The `Message` object has a `role` (either "user" or "agent") and a list of `parts`. Parts are where the actual content lives. We've already covered the three part types: `TextPart`, `FilePart`, and `DataPart`.

> The server responds with a `Task` object containing: `id`, `sessionId`, `status` (which holds the current state), `artifacts` (the outputs), and optionally `history` (the conversation log).

> An `Artifact` has a `name`, optional `description`, a list of `parts`, an `index` (for multi-artifact responses), and `lastChunk` (a boolean for streaming, indicating whether this is the final chunk of content).

---

## Slide 9 — Section 3: Tasks — Python SDK Code

**What's on screen:** Python code sending a task and reading the artifact.

**What to say:**
> Here's what creating a task looks like in code. You build a `TaskSendParams` with a fresh UUID as the `id`, wrap your query in a `Message` with role "user" and a `TextPart`, then call `client.send_task()`.

> The response is a `Task` object. To get the result, you navigate to `task.artifacts[0].parts[0].data` — the first artifact, first part, data field. That `data` field is a Python dict with the structured JSON the agent returned.

> The UUID is client-generated — you own the task ID. This is important for the input-required flow, where you need to reuse the same ID to resume the task. It's also important for idempotency — if your request times out and you retry with the same ID, the server won't create a duplicate task.

---

## Slide 10 — Section 4: Task Lifecycle

**What's on screen:** State machine diagram (same as Concepts deck slide 10).

**What to say:**
> A task moves through a defined state machine. We covered this in the concepts deck, but let's reinforce it in the tutorial context.

> `submitted` → `working` is the standard progression on every task. From `working`, there are four exits: `completed` (success), `failed` (error), `canceled` (client called tasks/cancel), and `input-required` (agent needs more info, as in the Booking Agent flow).

> In our tutorial, we demonstrate every state. The Flight Agent uses `submitted → working → completed`. The Booking Agent uses `input-required` three times before completing. And in Section 10 we deliberately trigger `failed` and `canceled` to demonstrate error handling.

---

## Slide 11 — Section 4: Task Lifecycle — Polling Pattern

**What's on screen:** Python polling code with tasks/get.

**What to say:**
> When you don't use streaming, you poll. The pattern is a simple loop: call `tasks/get` with the task ID, check `task.status.state`, and break when you hit a terminal state — `completed`, `failed`, or `canceled`.

> We also demonstrate `tasks/cancel` in the tutorial. You can call it on any task in `submitted` or `working` state. Once a task is in a terminal state, `tasks/cancel` will return a `TaskNotCancelable` error — a good test of your error handling.

> The `history` field on the task (when requested via `historyLength`) gives you the full conversation log — every message that was exchanged during the task. The Flight Agent enables `stateTransitionHistory` in its capabilities, which gives you even finer-grained insight into every state change.

---

## Slide 12 — Section 5: SSE Streaming — Client Side

**What's on screen:** Python code using send_task_streaming and consuming SSE events.

**What to say:**
> For real-time results, use `tasks/sendSubscribe`. The client opens an SSE connection and receives a stream of events.

> There are two event types. `TaskStatusUpdateEvent` fires when the task state changes — you'll see `submitted`, then `working`, then eventually `completed`. `TaskArtifactUpdateEvent` fires when the agent emits a chunk of output.

> The `lastChunk` field on an artifact event tells you whether the stream is done. You break when you see `lastChunk: true`. Until then, you can render each chunk as it arrives — just like streaming output from a language model.

> In our tutorial, the Flight Agent streams one flight result at a time. The Weather Agent streams one day's forecast at a time. The user sees results appearing live rather than waiting for the full batch.

---

## Slide 13 — Section 5: SSE Streaming — Server Side

**What's on screen:** Python server-side code using EventQueue.

**What to say:**
> On the server side, implementing streaming is straightforward. Inside your `AgentExecutor.execute()` method, you receive an `EventQueue`. You emit events by calling `event_queue.enqueue_event()`.

> The pattern is: first emit a `TaskStatusUpdateEvent` with state "working" and `final=False`. Then, for each chunk of output, emit a `TaskArtifactUpdateEvent` with `lastChunk: False`. When you're done, emit the last artifact with `lastChunk: True`, then emit a final `TaskStatusUpdateEvent` with state "completed" and `final=True`.

> The ADK framework automatically formats these events as SSE, handles the HTTP connection lifecycle, and routes them to the right client. Your code just enqueues events — you never touch HTTP or SSE directly.

---

## Slide 14 — Section 6: Multimodal Content

**What's on screen:** FilePart variants table, DataPart example, PDF upload code.

**What to say:**
> The Hotel Agent demonstrates A2A's multimodal capabilities. It accepts PDF brochures as input alongside text queries.

> `FilePart` has two variants. **Inline bytes** — you base64-encode the file and embed it directly in the message. Good for smaller files like images or short documents where you want self-contained messages. **URI reference** — you pass a URL pointing to the file hosted on S3, GCS, or any HTTPS endpoint. Good for large files where you don't want to bloat the message payload.

> In both cases, you include the `mimeType` so the receiving agent knows how to interpret the content. The Hotel Agent's Agent Card declares `inputModes: ["application/pdf"]` for this skill, so an orchestrator knows to send PDFs to this agent.

> The response from the Hotel Agent comes back as a `DataPart` — structured JSON with hotel names, prices, ratings, and amenities extracted from the PDF. The orchestrator can parse this programmatically rather than having to parse natural language text.

---

## Slide 15 — Section 7: Input Required

**What's on screen:** Multi-step booking loop code.

**What to say:**
> The Booking Agent uses the input-required pattern for a multi-step booking flow. When the agent needs more information, it transitions to `input-required` state and puts its question in `status.message`.

> The client pattern is a while loop. Check `task.status.state`. If it's `"input-required"`, read the question from `task.status.message.parts[0].text`, get the user's answer, and call `tasks/send` again with the **same task ID** but a new message containing the answer. The server resumes the same task.

> In our tutorial this happens three times: the agent asks for seat class, then meal preference, then loyalty program number. Each pause is an `input-required` state. After the third answer, the task transitions to `completed` with the booking confirmation as an artifact.

> The key insight: reusing the same task ID is what makes this a continuation, not a new task. The server associates the follow-up message with the existing task context.

---

## Slide 16 — Section 8: Push Notifications

**What's on screen:** Webhook registration code and FastAPI webhook receiver.

**What to say:**
> Push notifications are for tasks that run too long to poll or stream. The Booking Agent uses this pattern for booking confirmation, which might take several minutes in a real system.

> The flow has three steps. First, start the task with `tasks/send`. Second, immediately register a webhook with `tasks/pushNotification/set`, passing a `PushNotificationConfig` with your webhook URL and a verification token. Third, your client is done — it can exit or do other work. The server will POST the full Task JSON to your webhook when the task completes.

> The webhook receiver is a FastAPI endpoint. The first thing it does is validate the token header — comparing it with constant-time comparison to prevent timing attacks. Then it reads the task ID and state from the payload, and processes the artifacts.

> The token verification step is critical. Without it, anyone who discovers your webhook URL could send spoofed task completions. Always validate.

---

## Slide 17 — Section 9: Authentication and Security

**What's on screen:** Python client-side auth code for Bearer and API Key, server middleware description.

**What to say:**
> Authentication in A2A follows a clean pattern: discover requirements from the Agent Card, then inject credentials into every request.

> For the **Flight Agent** (Bearer token): fetch the Agent Card, read `authentication.schemes` which will be `["Bearer"]`, then create the `A2AClient` with an `httpx.AsyncClient` that has `Authorization: Bearer <token>` pre-configured in its headers.

> For the **Hotel Agent** (API Key): same discovery step, but the header is `X-API-Key` with the key value from your environment.

> The `A2ACardResolver` class handles the card fetch. The `A2AClient` handles all task operations. By passing different `httpx.AsyncClient` instances with different default headers, you get per-agent credential injection with no boilerplate in your task-sending code.

> For error handling, catch `A2AClientHTTPError`. If `status_code == 401`, your token is expired or invalid — refresh and retry. If `403`, you don't have permission — don't retry, escalate to the user.

---

## Slide 18 — Section 10: Error Handling — Error Codes

**What's on screen:** Table of JSON-RPC and A2A-specific error codes.

**What to say:**
> A2A uses standard JSON-RPC 2.0 error codes in the -32700 to -32603 range for protocol-level errors. These cover malformed JSON, invalid requests, unknown methods, bad parameters, and internal server exceptions.

> A2A also defines five protocol-specific error codes starting at -32001: `TaskNotFound` when you poll for a task ID that doesn't exist, `TaskNotCancelable` when you try to cancel a completed task, `PushNotificationNotSupported` when you try to set a webhook on an agent that hasn't declared `pushNotifications: true`, `UnsupportedOperation` when a method exists but the agent hasn't implemented it, and `ContentTypeNotSupported` when you send a MIME type the agent's skill doesn't accept.

> Knowing these error codes lets you write precise error handling — retry on `InternalError`, don't retry on `TaskNotCancelable`, surface `ContentTypeNotSupported` as a client configuration error.

---

## Slide 19 — Section 10: Error Handling — Recovery Patterns

**What's on screen:** Python retry and timeout code.

**What to say:**
> Three resilience patterns to implement in any production A2A client.

> **Exponential backoff** for transient errors. Catch `A2AClientHTTPError` for HTTP-level failures. Retry on 5xx server errors with an exponentially increasing wait and a bit of random jitter to prevent thundering herd. **Do not retry** on 401 or 403 — those are auth failures that won't resolve themselves. **Do not retry** when a task itself returns `failed` state — that's the agent telling you it can't complete the work.

> **Timeout and cancel** — wrap your `send_task` call in `asyncio.wait_for()` with a timeout. If it fires, immediately call `tasks/cancel` with the task ID. This prevents zombie tasks accumulating on the server. In our tutorial, we set a 30-second timeout on weather queries.

> **Graceful degradation** — in the orchestrator, if one agent fails, don't fail the entire trip plan. If the flight agent is unavailable, show an error for that section but still return hotel and weather results. Users get partial information rather than a complete failure.

---

## Slide 20 — Section 11: Multi-Agent Orchestration

**What's on screen:** TravelOrchestrator class code with setup and plan_trip methods.

**What to say:**
> The orchestrator is where everything comes together. The `TravelOrchestrator` class is itself an ADK `LlmAgent`. At startup, its `setup()` method fetches the Agent Card from each of the four specialist agents and creates an `A2AClient` for each — pre-configured with the right auth headers.

> When a travel query comes in, `plan_trip()` uses `asyncio.gather()` to fan out to the flight, hotel, and weather agents in parallel. All three tasks run concurrently. The total time is determined by the slowest agent, not the sum of all agents.

> After those three complete, the orchestrator sends the booking agent a sequential task, passing in the flight and hotel data it just received. Booking is sequential because it depends on the earlier results — you need to know which flight and hotel you're booking before you can book them.

---

## Slide 21 — Section 11: Orchestration — Routing and Aggregation

**What's on screen:** Routing code with capability checking, aggregation code, 9-step execution flow.

**What to say:**
> The orchestrator checks each agent's capabilities before choosing how to call it. If `card.capabilities.streaming` is true, it uses `sendSubscribe`. Otherwise, it uses synchronous `send`. This is dynamic — you don't hardcode which agents are streaming; you read it from the card at runtime.

> Aggregation pulls `DataPart` content out of each artifact and combines it into a single unified response dict with keys for flights, hotels, weather, and booking. The `totalCost` is computed by summing the flight and hotel prices from the structured data.

> The execution flow diagram on the right shows the 9 steps: fetch cards at startup, receive user query, match intent to agents, parallel fan-out to three agents, await all three, sequential booking, aggregate all four results, return the itinerary to the user. This is the complete picture of A2A orchestration.

---

## Slide 22 — Section 12: Running the Complete System — Port Map

**What's on screen:** Port map table for all 6 services, quick start commands.

**What to say:**
> The complete system runs six services, each on a dedicated port.

> Flight Agent on 8001 with Bearer auth, Hotel Agent on 8002 with API Key, Booking Agent on 8003 with no auth (but requires push notification token for the webhook), Weather Agent on 8004 with no auth, the Travel Orchestrator on 8010, and the Webhook Receiver on 9000.

> To start everything: `docker-compose up --build`. To run the end-to-end scenario: `python client/main.py "Plan a 5-day trip to Paris in December"`. You'll see agent card discovery, parallel streaming output from flight and weather, the hotel multimodal response, the booking input-required loop, and finally the webhook notification firing when booking confirms.

> Before running, create a `.env` file with three values: `FLIGHT_BEARER_TOKEN`, `HOTEL_API_KEY`, and `WEBHOOK_TOKEN`.

---

## Slide 23 — Section 12: Docker Compose Configuration

**What's on screen:** docker-compose.yml and agent server boilerplate code.

**What to say:**
> The docker-compose file is straightforward. Each agent is a separate service built from its own directory. Environment variables come from the `.env` file. The `orchestrator` service uses `depends_on` to ensure all four specialist agents are healthy before it starts.

> On the right is the boilerplate for any A2A agent using ADK. You define an `AgentCard` with your capabilities, create a `DefaultRequestHandler` wired to your `AgentExecutor` and an `InMemoryTaskStore`, then pass both to `A2AStarletteApplication`. Call `.build()` to get a standard FastAPI/Starlette ASGI app that you run with uvicorn.

> The framework automatically serves the Agent Card at `/.well-known/agent.json` and routes all JSON-RPC requests to your executor. You implement one method — `execute()` — and everything else is handled for you.

---

## Slide 24 — Section 12: End-to-End Request Flow

**What's on screen:** 10-step trace table.

**What to say:**
> Let's trace a user query through the entire system. This table shows every step.

> Step 1: the user runs the client with a natural-language query. Step 2: the Orchestrator parses the intent and identifies three parallel subtasks. Step 3: it fetches Agent Cards from all four agents. Step 4: it launches flight, hotel, and weather tasks concurrently with `asyncio.gather()`.

> Steps 5, 6, 7 run in parallel: Flight streams results via SSE, Hotel processes a PDF brochure, Weather streams a 5-day forecast.

> Step 8 is sequential: the Booking Agent runs an input-required loop — potentially three round trips for seat class, meal preference, and loyalty number.

> Step 9: the orchestrator aggregates all four artifacts into a unified itinerary dict. Step 10: the client prints the formatted travel plan with the booking reference.

---

## Slide 25 — Complete A2A Feature Coverage

**What's on screen:** Table mapping every A2A feature to the tutorial section that demonstrates it.

**What to say:**
> This table is a completeness check. Every feature defined in the A2A specification is demonstrated somewhere in this tutorial.

> All three Part types — TextPart, FilePart (both inline and URI), DataPart. All six task states. Both update delivery patterns — SSE streaming and push notifications. Both auth schemes — Bearer and API Key. All the push notification operations. Parallel fan-out and sequential chaining. The complete error code set. The stateTransitionHistory capability.

> If there's a specific feature you want to understand in depth, find it in this table and go to the corresponding section.

---

## Slide 26 — Sample Client Run — Terminal Output

**What's on screen:** Simulated terminal output of the full client run.

**What to say:**
> This is what you'll see when you run `client/main.py`. At the top, agent card discovery — four agents found, their capabilities logged. Then the parallel fan-out begins.

> You can see the flight results streaming in one by one — each flight appears on its own line as the SSE events arrive. Similarly the weather forecast arrives incrementally. The hotel response is synchronous — it sends the PDF, waits for the structured response, then logs the hotel list.

> Then the booking agent starts. Three `input-required` pauses, each displaying the agent's question. The user types an answer. After the third answer, `Status: completed` with a booking confirmation reference.

> Finally, the aggregated itinerary is printed: flight details, hotel choice, weather summary, total cost, and booking reference. This is what your users will experience end-to-end.

---

## Slide 27 — Deep Dive: AgentExecutor Pattern

**What's on screen:** Full HotelAgentExecutor implementation code, AgentExecutor interface description.

**What to say:**
> The `AgentExecutor` is the core pattern you'll implement for every A2A agent. You subclass it and implement one async method: `execute(context, event_queue)`.

> `context` gives you everything about the incoming request: `context.message` (the message with all its parts), `context.task_id`, and `context.session_id`.

> `event_queue` is how you send output back. You always emit in this order: first a `working` status with `final=False`, then one or more `TaskArtifactUpdateEvent` with your content, then a final status event with `final=True`.

> The Hotel Agent code walks through a complete implementation. It iterates over the message parts, extracts the text query and any PDF bytes, signals `working`, calls its business logic (`_search_hotels`), wraps the result in a `DataPart` inside an `Artifact`, emits it, then emits `completed`. Every agent follows this same pattern.

> For input-required, you emit an `input-required` status with the question in `status.message`, set `final=True` to end the current stream, and return. The client will call again with the same task ID.

---

## Slide 28 — Deep Dive: Booking Agent — Input-Required Server

**What's on screen:** BookingAgentExecutor code with multi-step state machine.

**What to say:**
> The Booking Agent's server-side is a state machine. Each time `execute()` is called, it checks what information it already has for the session and asks for what's missing.

> The session state is stored in a dict keyed by `session_id`. On the first call, there's no `seat_class` in the state, so it saves the initial booking data and emits `input-required` asking for seat class. On the second call, `seat_class` is missing from state but the data was saved, so it stores the seat class answer and asks for meal preference. And so on.

> Each `input-required` event has `final=True` — this closes the current SSE stream. The client will open a new one when it sends the follow-up.

> For production use, replace the in-memory dict with Redis and set a TTL so abandoned sessions don't accumulate. You should also validate each answer before storing it — don't trust raw user input in your booking logic.

---

## Slide 29 — Deep Dive: SessionId and Task History

**What's on screen:** Code using sessionId across multiple tasks and retrieving task history.

**What to say:**
> `sessionId` groups related tasks under one logical conversation. You generate it once — typically a UUID with a meaningful prefix — and pass it on every task in the session.

> In our tutorial, the orchestrator generates a `travel-session-<uuid>` ID at the start of each trip-planning request. All four agent tasks for that request share the same session ID. This lets agents that have access to session context know they're all part of the same travel plan.

> To retrieve task history, call `tasks/get` with a `historyLength` parameter. The response includes a `task.history` list of Message objects — the last N turns of the conversation. This requires the agent to have `stateTransitionHistory: true` in its Agent Card capabilities.

> The distinction between `history` and `artifacts` is important: `history` is the conversation transcript — messages sent back and forth. `artifacts` are the deliverable outputs — the files, data, and documents the agent produced.

---

## Slide 30 — Summary and Key Takeaways

**What's on screen:** Six takeaway boxes covering all major areas.

**What to say:**
> Six areas to take away from this tutorial.

> **A2A Protocol** — open standard, HTTP + JSON-RPC 2.0, framework-agnostic. Agent Cards enable automatic discovery.

> **Tasks and Lifecycle** — every interaction is a Task with a UUID. Six states. Poll with `tasks/get` or stream with `tasks/sendSubscribe`.

> **Content Types** — TextPart for text, FilePart for files (inline or URL), DataPart for structured machine-readable JSON.

> **Advanced Features** — SSE streaming for real-time output, input-required for multi-step human-in-the-loop, push notifications for fire-and-forget async.

> **Security** — Bearer tokens and API Keys declared in the Agent Card, auto-discovered by clients. Always validate on every server request.

> **Orchestration** — parallel fan-out with `asyncio.gather()`, sequential chaining for dependencies, graceful degradation when agents fail.

---

## Slide 31 — Next Steps and Resources

**What's on screen:** Resource links, code listing, extension ideas, best practices.

**What to say:**
> You've now seen every A2A feature in a complete, runnable system. Where to go from here?

> **Extend the project** — add a Car Rental agent to practice creating a new A2A skill from scratch. Add OAuth2 to the Booking Agent. Replace `InMemoryTaskStore` with Redis for production-grade task persistence. Add OpenTelemetry tracing to get distributed traces across all four agents.

> **Best practices to remember**: always validate Agent Cards before sending tasks; use `asyncio.gather()` for parallel fan-out; handle all task states including `input-required` — don't assume tasks always complete immediately; set timeouts and cancel on timeout; use `DataPart` for machine-readable outputs so orchestrators can parse results programmatically; never store sensitive data in task history.

> **Resources**: A2A spec at `a2a-protocol.org`, SDKs at `github.com/google-a2a`, ADK docs at `google.github.io/adk-docs`. Install the Python SDK with `pip install google-a2a`.

> Thank you — and happy building.

---

*End of Presenter Guide*
