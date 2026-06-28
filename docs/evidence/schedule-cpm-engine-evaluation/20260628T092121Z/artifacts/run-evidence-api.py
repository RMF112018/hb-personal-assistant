import os
import uvicorn

from hb_assistant.construction.analytics.api import create_app

db_path = os.environ["HB_ASSISTANT_DB_PATH"]
print(f"Starting evidence API with explicit db_path={db_path}")

app = create_app(db_path=db_path)

uvicorn.run(
    app,
    host="127.0.0.1",
    port=8000,
    log_level="info",
)
