import { createContext, useContext } from "react";
import type { Meta } from "./api";

/** Seasons, teams and data source from GET /meta, loaded once by App. */
export const MetaContext = createContext<Meta | undefined>(undefined);

export const useMeta = () => useContext(MetaContext);

/** Footnote under every probability chart. */
export const CHART_NOTE = "Model estimate • not a guarantee";
