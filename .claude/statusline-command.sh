#!/bin/sh
input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name')
style=$(echo "$input" | jq -r '.output_style.name // "default"')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Context usage
if [ -n "$used" ]; then
  used_display=$(printf "%.0f%%" "$used")
  context_part="Context: ${used_display} used"
else
  context_part="Context: --"
fi

printf '%s  |  Model: %s  |  Style: %s' "$context_part" "$model" "$style"
