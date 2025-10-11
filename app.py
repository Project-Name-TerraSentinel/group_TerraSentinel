from flask import Flask, request, jsonify
import onnxruntime as ort
import numpy as np

app = Flask(__name__)

# Load the ONNX model once
session = ort.InferenceSession("terra_pulse_model.onnx")

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        features = np.array([[
            data["NDVI_mean_early"],
            data["NDVI_median_early"],
            data["NDVI_std_early"],
            data["NDVI_mean_late"],
            data["NDVI_median_late"],
            data["NDVI_std_late"],
            data["NDVI_delta_mean"]
        ]], dtype=np.float32)

        inputs = {session.get_inputs()[0].name: features}
        outputs = session.run(None, inputs)
        prediction = int(outputs[0][0])

        return jsonify({"prediction": prediction, "status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
