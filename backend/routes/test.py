from flask import Blueprint, jsonify

test_bp = Blueprint("test", __name__)

@test_bp.route("/api/hello-test", methods=["GET"])
def hello_test():
    print("✅ test_bp funcionando correctamente en Railway")
    return jsonify({"message": "Hola desde test_bp 👋"}), 200
