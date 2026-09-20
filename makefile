reinstall:
	uv tool install --reinstall .

readme-completions:
	uv run bencher --print-completion zsh > ~/.config/zsh/completions/_bencher
	uv run bencher --print-completion fish > ~/.config/fish/completions/bencher.fish
	uv run bencher --print-completion bash > ~/.config/bash/completions/bencher.bash
