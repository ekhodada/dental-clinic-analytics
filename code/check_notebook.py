"""I execute the exploration notebook as a reproducibility check."""

import nbformat
from nbclient import NotebookClient
from .clean_and_refresh import BASE


def main():
    """I run every exploration cell and save its checked outputs."""
    path = BASE / "notebooks/exploration.ipynb"
    notebook = nbformat.read(path, as_version=4)
    NotebookClient(notebook, timeout=120, kernel_name="python3").execute()
    nbformat.write(notebook, path)
    print("Exploration: every cell completed.")


if __name__ == "__main__":
    main()
