/*
 * Stub linkato con mnemo_embedded_bytecode.c e libvm (-lvm).
 * vm_run_from_string_quiet: nessun «=== VM dump ===» a fine esecuzione.
 */
extern const char mnemo_embedded_bytecode[];

void vm_run_from_string_quiet(const char *bytecode);

int main(void)
{
    vm_run_from_string_quiet(mnemo_embedded_bytecode);
    return 0;
}
