import ctypes
import time
import sys

# Constante Windows pour simuler un mouvement de souris
MOUSEEVENTF_MOVE = 0x0001

def keep_alive():
    print("No-sleep mode ON")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            # On simule un micro-déplacement relatif (0 pixel)
            # C'est suffisant pour que Windows et Teams réinitialisent leur timer d'inactivité
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0)
            
            # Optionnel : empêche aussi l'écran de s'éteindre logiciellement
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
            
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nScript arrêté.")
        # Rend la main au système pour la gestion de l'énergie normale
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

if __name__ == "__main__":
    keep_alive()