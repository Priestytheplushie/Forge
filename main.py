import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from forge.app import ForgeApp

if __name__ == "__main__":
    app = ForgeApp()
    app.mainloop()
