import google.generativeai as genai
from config.settings import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

# Test tous les modèles disponibles
models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemma-3-4b-it",
]

for model_name in models_to_test:
    print(f"\nTest avec {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say hello in one word.")
        print(f"✅ {model_name} fonctionne ! Réponse: {response.text[:50]}")
        break
    except Exception as e:
        print(f"❌ {model_name} : {str(e)[:80]}")