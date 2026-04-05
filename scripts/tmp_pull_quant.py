from pathlib import Path
import json
from huggingface_hub import snapshot_download

candidates = [
    'Qwen/Qwen2.5-Coder-14B-Instruct-AWQ',
    'Qwen/Qwen2.5-Coder-7B-Instruct-AWQ',
    'Qwen/Qwen2.5-Coder-32B-Instruct-AWQ',
]
out = Path('.models')
out.mkdir(exist_ok=True)
picked = None
errors = {}
for repo in candidates:
    try:
        target = out / repo.replace('/', '--')
        snapshot_download(repo_id=repo, local_dir=str(target), local_dir_use_symlinks=False, resume_download=True)
        picked = {'repo': repo, 'path': str(target)}
        break
    except Exception as ex:
        errors[repo] = str(ex)

result = {'picked': picked, 'errors': errors}
state_dir = Path('bus/state')
state_dir.mkdir(parents=True, exist_ok=True)
(state_dir / 'codemage_quant_choice.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
