import json
import os
import uuid

import gradio as gr
import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL")
STREAM_URL = f"{BACKEND_URL}/stream"

SESSION_ID = str(uuid.uuid4())

FALLBACK_ERROR = (
    "The travel planner is temporarily unavailable. "
    "Please try again in a moment."
)

def stream_chat(message: str):
    payload = {"message": message, "session_id": SESSION_ID}
    try:
        with requests.post(
            STREAM_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()

            event_name = None
            data_line = None

            for raw_line in response.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue

                line = raw_line.strip("\r")

                if line == "":
                    if event_name is not None and data_line is not None:
                        try:
                            data = json.loads(data_line)
                        except json.JSONDecodeError:
                            data = {}
                        yield event_name, data
                    event_name, data_line = None, None
                    continue

                if line.startswith("event:"):
                    event_name = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_line = line[len("data:"):].strip()

    except requests.exceptions.RequestException as exc:
        print(f"Backend connection error: {exc}")
        yield "error", {"message": FALLBACK_ERROR, "error": str(exc)}

def respond(message, history):
    if not message or not message.strip():
        yield history, history, "", gr.update(value="")
        return

    history = list(history or [])
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": ""})

    status = ""
    assistant_text = ""

    yield history, history, status, gr.update(value="", interactive=False)

    for event_name, data in stream_chat(message):
        if event_name == "activity":
            status = f" {data.get('label', 'Working…')}"
            yield history, history, status, gr.update(interactive=False)

        elif event_name == "token":
            assistant_text += data.get("text", "")
            history[-1]["content"] = assistant_text
            yield history, history, status, gr.update(interactive=False)

        elif event_name == "error":
            status = ""
            error_msg = data.get("message", FALLBACK_ERROR)
            history[-1]["content"] = f" **Something went wrong**\n\n{error_msg}"
            yield history, history, status, gr.update(interactive=True)
            return

        elif event_name == "done":
            status = ""
            final_text = data.get("response", assistant_text) or assistant_text

            history[-1]["content"] = final_text
            yield history, history, status, gr.update(interactive=True)
            return

    if not history[-1]["content"]:
        history[-1]["content"] = f" **Something went wrong**\n\n{FALLBACK_ERROR}"
    yield history, history, status, gr.update(interactive=True)


CUSTOM_CSS = """
:root {
    --tw-sky: #1e88e5;
    --tw-sand: #f5deb3;
    --tw-deep: #0d3b66;
    --tw-sunset: #f77f00;
}

.gradio-container {
    max-width: 900px;
    margin: 0 auto;
    font-family: 'Segoe UI', system-ui, sans-serif;
}

#tw-header {
    background: linear-gradient(135deg, #198bc0 0%, #1c9bd7 100%);
    color: white;
    padding: 24px 20px;
    border-radius: 16px;
    text-align: center;
    margin-bottom: 12px;
}

#tw-header h1 {
    margin: 0;
    font-size: 32px;
}

#tw-header p {
    margin: 4px 0 0;
    opacity: 0.9;
    font-size: 16px;
}

#tw-chatbot {
    border-radius: 14px;
    border: 1px solid var(--tw-sand);
}

#tw-send-row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
}

#tw-status {
    min-height: 5.4px;
    color: var(--tw-sunset);
    font-weight: 600;
    padding-left: 4px;
}

@media (max-width: 600px) {
    #tw-header h1 { font-size: 32px; }
    #tw-header { padding: 16px 12px; }
    .gradio-container { padding: 4px; }
}
"""

def main():
    with gr.Blocks(
        title="TripWeaver — Multi-Agent Travel Planner",
    ) as demo:
        history_state = gr.State([])
        gr.HTML(
            """
            <div id="tw-header">
                <h1> TripWeaver</h1>
                <p>Your Multi-agent travel planning assistant</p>
            </div>
            """
        )

        chatbot = gr.Chatbot(
            elem_id="tw-chatbot",
            height=480,
            avatar_images=(None, None),
        )

        status_display = gr.Markdown("", elem_id="tw-status")
        
        with gr.Row(elem_id="tw-send-row"):
            message = gr.Textbox(
                label="",
                placeholder="Find me flights from AAA to BBB on YYYY-MM-DD",
                scale=8,
                container=False,
            )
            submit = gr.Button("Send ", variant="primary", scale=1)

        gr.Examples(
            examples=[
                "Find hotels in Paris for July 20-25",
                "Show all flights",
                "Book flight from JFK to LAX on 2026-08-01",
            ],
            inputs=message,
        )

        submit.click(
            respond,
            inputs=[message, history_state],
            outputs=[chatbot, history_state, status_display, message],
        )
        message.submit(
            respond,
            inputs=[message, history_state],
            outputs=[chatbot, history_state, status_display, message],
        )

    demo.launch(
       server_name="0.0.0.0",
       server_port=int(os.environ.get("PORT", 7860)),
       theme=gr.themes.Soft(primary_hue="blue", secondary_hue="orange"),
       css=CUSTOM_CSS,
   )


if __name__ == "__main__":
    main()
