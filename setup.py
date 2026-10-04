"""
Quick setup script — creates necessary directories and validates the environment.
Run: python setup.py
"""
import os
import sys


def check_env():
    print("🔍 Checking environment...")
    if sys.version_info < (3, 11):
        print(f"  ❌ Python 3.11+ required (found {sys.version})")
        sys.exit(1)
    print(f"  ✅ Python {sys.version.split()[0]}")


def create_dirs():
    print("\n📁 Creating directories...")
    dirs = ["data", "logs", "screenshots", "workspace_files"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"  ✅ {d}/")


def check_dotenv():
    print("\n⚙️  Checking .env...")
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("  ⚠️  .env created from .env.example — please add your OPENAI_API_KEY")
        else:
            print("  ❌ No .env file found. Create one with your OPENAI_API_KEY.")
    else:
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("OPENAI_API_KEY", "")
        if not key or key.startswith("sk-your"):
            print("  ⚠️  OPENAI_API_KEY not set in .env — agent will fail without it")
        else:
            print(f"  ✅ OPENAI_API_KEY found (ending ...{key[-6:]})")


def check_playwright():
    print("\n🌐 Checking Playwright...")
    try:
        import playwright
        print("  ✅ playwright installed")
        # Check if browser is installed
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            print("  ✅ Chromium browser available")
        except Exception as e:
            print(f"  ⚠️  Chromium not installed. Run: playwright install chromium")
    except ImportError:
        print("  ❌ playwright not installed. Run: pip install playwright")


def main():
    print("=" * 50)
    print("  Autonomous AI Worker — Setup")
    print("=" * 50)

    check_env()
    create_dirs()
    check_dotenv()
    check_playwright()

    print("\n" + "=" * 50)
    print("  Setup complete!")
    print("\nNext steps:")
    print("  1. Edit .env and add your OPENAI_API_KEY")
    print("  2. Terminal 1:  python run_mock_app.py")
    print("  3. Terminal 2:  python run_api.py")
    print("  4. Browser:     open frontend/index.html")
    print("  5. CLI test:    python cli.py demo")
    print("=" * 50)


if __name__ == "__main__":
    main()
