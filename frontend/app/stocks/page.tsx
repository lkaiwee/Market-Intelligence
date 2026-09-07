import { Suspense } from "react";

import { Loading } from "@/components/Loading";
import StockDetails from "./StockDetails";

export default function StockDetailPage() {
  return (
    <Suspense fallback={<Loading />}>
      <StockDetails />
    </Suspense>
  );
}
