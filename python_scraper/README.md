# OPIS Manager - Python Scraper

*Note: For the general architecture and database configuration, please refer to the [main README](../README.md) and the [OPIS Manager Core](https://github.com/UNICT-DMI/opis-manager-core) repository.*

A Python tool designed to extract OPIS evaluation data for the academic years spanning from 2021/2022 to 2024/2025.

## 1. Prerequisites
- **Python 3.11+**

## 2. Configuration

### Option A (Recommended): VS Code + Dev Containers 
The environment is already containerized and ready to use.
1. Install the **Dev Containers** extension in VS Code.
2. Open the `python_scraper` folder in VS Code.
3. Click on the *Reopen in Container* popup or use the Command Palette (`Ctrl+Shift+P`) and select **Dev Containers: Rebuild and Reopen in Container**. The environment will automatically download Python and install dependencies, including some useful pre-configured extensions.

### Option B: Manual Setup

```bash
cd python_scraper
python -m venv .venv
source .venv/bin/activate  
pip install -r requirements.txt
```

### Environment Variables
Create a `.env` file in `python_scraper` folder as described in the [OPIS Manager Core](https://github.com/UNICT-DMI/opis-manager-core) (the DB must already be initialized via its migrations).
Simply add the `DEBUG_MODE` variable to your existing `.env` file:
```env
DEBUG_MODE=false
```
*(Tip: Set `DEBUG_MODE=true` to run the scraper on a small random sample of data during development).*

## 3. Execution
```bash
python -m src.main
```

## 4. CI Pipeline: How to keep the build from failing
This project uses GitHub Actions to enforce code quality. Before making a `git push`, run these three local commands to avoid getting your Pull Request blocked:

1. **Auto-formatting:**
   ```bash
   black src tests
   ```
2. **Static type checking:**
   ```bash
   pyright src tests
   ```
3. **Running tests (Minimum coverage threshold: 80%):**
   ```bash
   pytest --cov=src --cov-fail-under=80
   ```