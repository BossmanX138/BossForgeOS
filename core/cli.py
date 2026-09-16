from .dataforge import DataForge  # Fixed: lowercase 'd' in filename
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

        # Also write ML.NET format by default - Fixed: added missing parameter
        from .writers import write_mlnet_format
        write_mlnet_format(merged, output_dir, forge.get_mlnet_format())

        # Write intermediate files for debugging
        for file in os.listdir(input_dir):
            if os.path.isfile(os.path.join(input_dir, file)):
                try:
                    df = forge._load_and_validate(file)
                    if not df.empty:
                        from .writers import write_intermediate
                        write_intermediate(df, file, output_dir)
                except Exception as e:
                    log.write(f"Error writing intermediate for {file}: {str(e)}\n")
