from .dataforge import DataForge
import os

def run(input_dir, output_dir, final_format):
    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/bad_rows.log", "w", encoding="utf8") as log:
        forge = DataForge(input_dir, output_dir, log)
        merged = forge.process_all()

        # Write standard format (default to CSV if not specified)
        if not final_format or final_format.lower() == "csv":
            from .writers import write_output
            write_output(merged, "csv", output_dir)

        # Also write the requested format if different from CSV
        if final_format and final_format.lower() != "csv":
            from .writers import write_output
            write_output(merged, final_format, output_dir)

        # Write ML.NET format - only create this one intermediate file
        from .writers import write_mlnet_format
        write_mlnet_format(merged, output_dir, forge.get_mlnet_format())

        # Clean up any temporary files that might have been created during processing
        _cleanup_temporaries(output_dir)

def _cleanup_temporaries(output_dir):
    """Remove any temporary files that might have been created."""
    temp_patterns = ["*.tmp", "*.temp", "~*"]
    for pattern in temp_patterns:
        for file in os.listdir(output_dir):
            if file.endswith(tuple(pattern.replace("*", "").split(","))):
                try:
                    os.remove(os.path.join(output_dir, file))
                except OSError:
                    pass
