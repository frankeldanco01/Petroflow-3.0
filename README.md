# Wildlife Monitoring App

Prototype site and FastAPI backend for lawful wildlife monitoring, habitat scoring, conservation planning, and retrieval routing.

## Files
- `index.html` - front-end preview site
- `wildlife_monitoring_app_starter.py` - backend API
- `requirements.txt` - Python packages
- `render.yaml` - Render deployment config
- `.gitignore` - Python ignore rules

## Run locally
```bash
pip install -r requirements.txt
uvicorn wildlife_monitoring_app_starter:app --reload
```

Then open:
- `http://127.0.0.1:8000/docs`
- `index.html` in your browser

## Deploy backend on Render
1. Create a new Web Service on Render
2. Connect this GitHub repo
3. Render should detect `render.yaml`
4. Deploy and copy the public API URL
5. Open `index.html` and paste the API URL into the endpoint box

## Publish the front-end
Enable GitHub Pages for this repository and publish from the root of the `main` branch.

## Notes
This prototype is for lawful monitoring and habitat analysis. It does not identify live animal positions for hunting.
