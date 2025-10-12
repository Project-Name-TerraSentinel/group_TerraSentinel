from flask import Flask, request, jsonify
import onnxruntime as ort
import numpy as np
import os
import sys

app = Flask(__name__)

# Load ONNX model safely using absolute path
MODEL_PATH = os.path.join(os.path.dirname(__file__), "terra_pulse_model.onnx")

if not os.path.exists(MODEL_PATH):
    print(f"ERROR: ONNX model not found at {MODEL_PATH}", file=sys.stderr)
    sys.exit(1)  # Exit immediately if the model is missing

try:
    session = ort.InferenceSession(MODEL_PATH)
except Exception as e:
    print(f"ERROR: Failed to load ONNX model: {e}", file=sys.stderr)
    sys.exit(1)

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()

        # Extract metadata
        location = data.get("location", "Unknown location")
        user_context = data.get("user_context", "General user")

        # Extract numeric features (7 NDVI columns)
        features = np.array([[ 
            data["NDVI_mean_early"],
            data["NDVI_median_early"],
            data["NDVI_std_early"],
            data["NDVI_mean_late"],
            data["NDVI_median_late"],
            data["NDVI_std_late"],
            data["NDVI_delta_mean"]
        ]], dtype=np.float32)

        # Run ONNX prediction
        inputs = {session.get_inputs()[0].name: features}
        outputs = session.run(None, inputs)
        prediction = float(outputs[0][0])

        # Convert model output to percentage / confidence
        degradation_risk = int(min(100, prediction * 100))
        confidence = round(min(1.0, abs(prediction)), 2)

        # Determine risk factors & recommended action
        if degradation_risk > 70:
            risk_factors = ["bare_soil_increase", "low_ndvi"]
            recommended_action_key = "mulch_crop_residue"
        elif degradation_risk > 40:
            risk_factors = ["moderate_ndvi_drop"]
            recommended_action_key = "increase_soil_cover"
        else:
            risk_factors = ["healthy_ndvi"]
            recommended_action_key = "maintain_current_practices"

        # Build final JSON output
        ml_output = {
            "location": location,
            "degradation_risk": degradation_risk,
            "risk_factors": risk_factors,
            "recommended_action_key": recommended_action_key,
            "confidence": confidence,
            "user_context": user_context
        }

        return jsonify({"ml_output": ml_output})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Debug=True for local testing, False for production on Render
    app.run(debug=True, host="0.0.0.0", port=5000)
