from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from traffic_model import MallTrafficModel


app = Flask(__name__)
model = MallTrafficModel()


def params_from_request() -> dict:
    data = request.get_json(silent=True) or {}
    return {
        "car_volume": float(data.get("carVolume", 28)),
        "motor_volume": float(data.get("motorVolume", 42)),
        "entry_flow": float(data.get("entryFlow", 35)),
        "exit_flow": float(data.get("exitFlow", 30)),
        "patience": float(data.get("patience", 18)),
        "seed": data.get("seed"),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/reset")
def reset():
    global model
    params = params_from_request()
    if params["seed"] in ("", None):
        params["seed"] = None
    else:
        params["seed"] = int(params["seed"])
    model = MallTrafficModel(**params)
    return jsonify(model.snapshot())


@app.post("/api/step")
def step():
    steps = int((request.get_json(silent=True) or {}).get("steps", 1))
    for _ in range(max(1, min(20, steps))):
        model.step()
    return jsonify(model.snapshot())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
