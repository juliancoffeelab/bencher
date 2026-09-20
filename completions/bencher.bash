# Run compgen with every argument passed to this function and append each
# generated candidate to COMPREPLY without splitting it on spaces.
#
# Arguments: the options and word passed directly to compgen.
# Output: candidates appended to the global COMPREPLY array.
#
# A read loop keeps this compatible with macOS's Bash 3.2, which lacks mapfile.
__bencher_compgen() {
    local candidate

    while IFS= read -r candidate; do
        COMPREPLY+=("$candidate")
    done < <(compgen "$@")
}

_bencher() {
    local current=${COMP_WORDS[COMP_CWORD]}
    COMPREPLY=()

    # Bencher owns the first argument. It may be an option or the command to run.
    if ((COMP_CWORD == 1)); then
        if [[ $current == -* ]]; then
            __bencher_compgen -W '-h --help --print-completion' -- "$current"
        else
            __bencher_compgen -c -- "$current"
        fi
        return
    fi

    case ${COMP_WORDS[1]} in
    -h | --help)
        return
        ;;
    --print-completion)
        if ((COMP_CWORD == 2)); then
            __bencher_compgen -W 'zsh fish bash' -- "$current"
        fi
        return
        ;;
    -*)
        return
        ;;
    esac

    # Let the wrapped command complete its own arguments when bash-completion
    # provides the helper. The second name supports older releases.
    if declare -F _comp_command_offset >/dev/null; then
        _comp_command_offset 1
    elif declare -F _command_offset >/dev/null; then
        _command_offset 1
    fi
}

complete -F _bencher bencher
