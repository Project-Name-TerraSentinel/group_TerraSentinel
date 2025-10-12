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

        # Extract metadata fields (location, user_context) if provided
        location = data.get("location", "Unknown location")
        user_context = data.get("user_context", "General user")

        # Extract NDVI-related features
        features = np.array([[
            data["NDVI_mean_early"],
            data["NDVI_median_early"],
            data["NDVI_std_early"],
            data["NDVI_mean_late"],
            data["NDVI_median_late"],
            data["NDVI_std_late"],
            data["NDVI_delta_mean"]
        ]], dtype=np.float32)

        # Run ONNX inference
        inputs = {session.get_inputs()[0].name: features}
        outputs = session.run(None, inputs)
        prediction = float(outputs[0][0])

        # 🌿 Derive interpretive metrics from prediction
        # You can adjust these to match your model scale
        degradation_risk = int(prediction * 100) if prediction <= 1 else int(prediction)
        confidence = round(min(1.0, abs(prediction) / 1.0), 2)

        # Risk factors and recommendation logic
        if degradation_risk > 70:
            risk_factors = ["bare_soil_increase", "low_ndvi"]
            recommended_action_key = "mulch_crop_residue"
        elif degradation_risk > 40:
            risk_factors = ["moderate_ndvi_drop"]
            recommended_action_key = "increase_soil_cover"
        else:
            risk_factors = ["healthy_ndvi"]
            recommended_action_key = "maintain_current_practices"

        # Combine everything into a structured output
        ml_output = {
            "location": location,
            "degradation_risk": degradation_risk,
            "risk_factors": risk_factors,
            "recommended_action_key": recommended_action_key,
            "confidence": confidence,
            "user_context": user_context
        }

        output = {"ml_output": ml_output}
        return jsonify(output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
