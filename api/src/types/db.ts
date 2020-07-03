/**
 * Types describing the rows returned by the database. May only partially describe the fields stored
 * in the database. Correspond to schemas in 'data-processing/common/models.py'
 */

interface PaperRow {
  s2_id: string;
  arxiv_id: string;
}

interface VersionRow {
  id: number;
  paper_id: string;
  index: number;
}

interface EntityRow {
  paper_id: string;
  id: number;
  version: number;
  type: string;
  source: string;
}

type EntityRowUpdates = Omit<EntityRow, "id" | "type" | "paper_id">;

interface BoundingBoxRow {
  id: number;
  entity_id: number;
  source: string;
  page: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

interface EntityDataRow {
  id: number;
  entity_id: number;
  source: string;
  type: EntityDataRowType;
  key: string;
  value: string | null;
}

type EntityDataRowType =
  | "scalar"
  | "reference"
  | "scalar-list"
  | "reference-list";
