function __bencher_can_delegate
    set --local first_argument \
        (commandline --current-process --tokens-expanded --cut-at-cursor)[2]

    if test -n "$first_argument"; and string match --quiet -- '-*' "$first_argument"
        return 1
    end

    return 0
end

# Bencher's own options.
complete --command bencher --no-files
complete \
    --command bencher \
    --condition __fish_use_subcommand \
    --short-option h \
    --long-option help \
    --description 'Show help'
complete \
    --command bencher \
    --condition __fish_use_subcommand \
    --long-option print-completion \
    --exclusive \
    --arguments 'zsh fish' \
    --description 'Print a shell completion script'

# Delegate everything after the wrapped command to that command's completer.
complete \
    --command bencher \
    --condition __bencher_can_delegate \
    --arguments '(__fish_complete_subcommand)'
