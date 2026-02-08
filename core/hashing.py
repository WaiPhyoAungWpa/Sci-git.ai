import hashlib
import os
import shutil

def get_file_hash(path):
    """Generates a SHA-256 hash of a file's content."""
    if not os.path.exists(path): return None
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ensure_vault(project_path):
    vault_path = os.path.join(project_path, ".sci_vault")
    os.makedirs(vault_path, exist_ok=True)
    return vault_path

def save_to_vault(file_path, project_path):
    """Copies file to vault named by its hash."""
    file_hash = get_file_hash(file_path)
    vault_dir = ensure_vault(project_path)
    dest = os.path.join(vault_dir, f"{file_hash}.csv")
    if not os.path.exists(dest):
        shutil.copy2(file_path, dest)
    return file_hash