// Names for the generated API types, so screens import `InquiryDetail` and not a path into
// schema.d.ts. Nothing here is hand-written API knowledge: change the API, regenerate, fix the
// compiler errors.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type InquiryDetail = Schemas["InquiryDetail"];
export type InquirySummary = Schemas["InquirySummary"];
export type InquiryList = Schemas["InquiryList"];
export type Draft = Schemas["Draft"];
export type DraftCheck = Schemas["DraftCheck"];
export type Escalation = Schemas["Escalation"];
export type Insights = Schemas["Insights"];
export type StatusResponse = Schemas["StatusResponse"];
export type ExportText = Schemas["ExportText"];
export type SettingsView = Schemas["SettingsView"];
export type Classification = Schemas["Classification"];
export type Extraction = Schemas["Extraction"];
export type Retrieval = Schemas["Retrieval"];
export type Source = Schemas["Source"];
export type AuditEvent = Schemas["AuditEvent"];
export type ReasonCode = Schemas["ReasonCode"];
export type CheckCode = Schemas["CheckCode"];
export type InquiryStatus = Schemas["InquiryStatus"];
export type Urgency = Schemas["Urgency"];
export type Route = Schemas["Route"];
export type ApiErrorBody = { error: { code: string; message: string; request_id: string } };
