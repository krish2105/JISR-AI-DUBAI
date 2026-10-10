/**
 * /[lang]/tariff — explore the UAE tariff and CEPA origin rules; see the duty agent's path for a product.
 */

import type { Metadata } from "next";
import { TariffExplorer } from "@/components/tariff/TariffExplorer";

export const metadata: Metadata = { title: "Tariff explorer" };

export default function TariffPage() {
  return <TariffExplorer />;
}
