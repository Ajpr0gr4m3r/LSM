"""Comprueba los detectores de Seña sin cámara, sin grabar y sin entrenar."""
import platform
import sys
import traceback
from importlib.metadata import PackageNotFoundError, version


def main():
    """Procesa imágenes vacías; devuelve 1 ante un fallo real y 0 si funcionan."""
    print(f"Python: {sys.version.split()[0]} | {platform.system()} {platform.machine()}", flush=True)
    print(f"Ejecutable: {sys.executable}", flush=True)
    for package in ("mediapipe", "numpy", "opencv-python", "opencv-contrib-python", "tensorflow"):
        try:
            installed = version(package)
        except PackageNotFoundError:
            installed = "no instalado con este nombre"
        print(f"{package}: {installed}", flush=True)
    print("El aviso 'Feedback manager requires a model with a single signature' "
          "no indica por sí solo un fallo. Esta prueba verifica la ejecución.", flush=True)
    try:
        import mediapipe as mp
        import numpy as np
        factories = (
            ("Holistic / seguimiento", lambda: mp.solutions.holistic.Holistic(
                model_complexity=1, min_detection_confidence=.5, min_tracking_confidence=.5)),
            ("Holistic / foto", lambda: mp.solutions.holistic.Holistic(
                static_image_mode=True, model_complexity=1, min_detection_confidence=.5)),
            ("Hands / recuperación", lambda: mp.solutions.hands.Hands(
                max_num_hands=2, model_complexity=1)),
            ("Hands / detalle", lambda: mp.solutions.hands.Hands(
                static_image_mode=True, max_num_hands=1)),
        )
    except Exception:
        traceback.print_exc()
        return 1
    failed = False
    for name, factory in factories:
        print(f"Probando {name}...", flush=True)
        try:
            with factory() as detector:
                for _ in range(3):
                    result = detector.process(np.zeros((256, 256, 3), dtype=np.uint8))
                    if result is None:
                        raise RuntimeError("El detector no devolvió un resultado")
            print(f"OK: {name}, 3 imágenes procesadas.", flush=True)
        except Exception:
            failed = True
            print(f"ERROR: {name}", flush=True)
            traceback.print_exc()
    print("Hay fallos: comparte la salida completa, incluido el Traceback." if failed else
          "Detectores operativos. Esta prueba no evalúa la cámara ni la precisión del modelo de señas.",
          flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
