// Témoin FD-ARCH-001 (tests seulement) : script d'éditeur qui échoue ; la ressource
// doit rester consultable (repli en lecture seule du client générique).
export function createResourceEditor() {
  throw new Error("témoin en échec");
}
