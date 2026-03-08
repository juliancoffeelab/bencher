# What

A simple gui program that allows you to spawn a command and track
its resource usage (only CPU and Memory for now).

Yes, heavily vibecoded.

# Installation
Use `uv tool`, or `pipx`
```bash
uv tool install --from git+https://github.com/juliancoffeelab/bencher.git bencher
```

# Screenshots
<img width="1022" height="650" alt="simple example of running Python Fibonacci script, shows cpu and memory" src="https://github.com/user-attachments/assets/c1704093-4205-41b0-9088-bf2cda734b2d" />
<img width="991" height="621" alt="example of summary, shows total duration, peak memory and other stats" src="https://github.com/user-attachments/assets/f0a80b0e-8772-4c13-a49e-a4df834db64a" />
<img width="988" height="616" alt="shows an example of cargo run, cpu going over 400%" src="https://github.com/user-attachments/assets/cd484008-e304-4270-9398-41f34e027802" />


# TODO
Maybe add CI and publish it to pypi?

P.s. when adding CI would be nice to run mypy over matrix of all OS-s
