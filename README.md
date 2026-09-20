# What

A simple gui program that allows you to spawn a command and track
its resource usage (only CPU and Memory for now).

Yes, heavily vibecoded (the hard way, by copypasting from a chat :P).

# Installation
Use `uv tool`, or `pipx`
```bash
uv tool install --from git+https://github.com/juliancoffeelab/bencher.git bencher
```

## Zsh completions
We also have zsh completions.

Please read how to install them in your ZSH configuration, in my case, it's
this:
```bash
bencher --print-completion zsh > ~/.config/zsh/completions/_bencher
```

## Fish completions
Fish loads completions from `~/.config/fish/completions`:
```bash
bencher --print-completion fish > ~/.config/fish/completions/bencher.fish
```

## Bash completions
My Bash config sources files from `~/.config/bash/completions`:
```bash
bencher --print-completion bash > ~/.config/bash/completions/bencher.bash
```

# Screenshots
<img width="1022" height="650" alt="simple example of running Python Fibonacci script, shows cpu and memory" src="https://github.com/user-attachments/assets/c1704093-4205-41b0-9088-bf2cda734b2d" />
<img width="991" height="621" alt="example of summary, shows total duration, peak memory and other stats" src="https://github.com/user-attachments/assets/f0a80b0e-8772-4c13-a49e-a4df834db64a" />
<img width="988" height="616" alt="shows an example of cargo run, cpu going over 400%" src="https://github.com/user-attachments/assets/cd484008-e304-4270-9398-41f34e027802" />


# TODO
Maybe add CI and publish it to pypi?

P.s. when adding CI would be nice to run mypy over matrix of all OS-s
