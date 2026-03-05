"use client";
import { useState } from "react";
import Link from "next/link";
import {
  ChevronDown, ChevronUp, ExternalLink, Mail, Phone,
  Globe, MapPin, AlertTriangle, Shield
} from "lucide-react";
import type { SupplierResult } from "@/lib/types";

const TYPE_LABELS: Record<string, string> = {
  manufacturer: "Производитель",
  distributor:  "Дистрибьютор",
  importer:     "Импортёр",
  exporter:     "Экспортёр",
  wholesaler:   "Оптовик",
  trader:       "Трейдер",
};

const ADAPTER_LABELS: Record<string, string> = {
  opencorporates: "OpenCorporates",
  gleif:          "GLEIF",
  kompass:        "Kompass",
  europages:      "Europages",
  alibaba:        "Alibaba",
  panjiva:        "Panjiva",
  importyeti:     "ImportYeti",
  volza:          "Volza",
  yellowpages:    "Yellow Pages",
  ec21:           "EC21",
  exporthub:      "ExportHub",
  tradekey:       "Tradekey",
  tridge:         "Tridge",
  exporters_india:"Exporters India",
  tradeindia:     "TradeIndia",
  direct_website: "Сайт компании",
};

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 85 ? "bg-green-500" : pct >= 65 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 text-sm">
      <div className="w-24 bg-gray-200 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-gray-500">{pct}%</span>
    </div>
  );
}

export function ResultCard({ supplier }: { supplier: SupplierResult }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`bg-white rounded-xl border shadow-sm overflow-hidden ${supplier.sanction_flag ? "border-red-300" : "border-gray-200"}`}>
      {/* Header */}
      <div className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-gray-400">#{supplier.rank}</span>
              <h2 className="font-semibold text-gray-900 truncate">{supplier.canonical_name}</h2>
              {supplier.canonical_country && (
                <span className="text-gray-500 text-sm shrink-0">{supplier.canonical_country}</span>
              )}
            </div>
            {/* Supplier types */}
            <div className="flex flex-wrap gap-1">
              {supplier.supplier_types.map(t => (
                <span key={t} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                  {TYPE_LABELS[t] ?? t}
                </span>
              ))}
            </div>
          </div>
          <div className="shrink-0 text-right space-y-1">
            <ConfidenceBar score={supplier.confidence_score} />
            <span className="text-xs text-gray-400">{supplier.source_count} источн.</span>
          </div>
        </div>

        {/* Contact info */}
        <div className="grid grid-cols-1 gap-1 text-sm text-gray-600">
          {supplier.canonical_email && (
            <a href={`mailto:${supplier.canonical_email}`} className="flex items-center gap-1.5 hover:text-blue-600">
              <Mail className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{supplier.canonical_email}</span>
            </a>
          )}
          {supplier.canonical_phone && (
            <span className="flex items-center gap-1.5">
              <Phone className="w-3.5 h-3.5 shrink-0" />
              {supplier.canonical_phone}
            </span>
          )}
          {supplier.canonical_website && (
            <a
              href={`https://${supplier.canonical_website}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 hover:text-blue-600"
            >
              <Globe className="w-3.5 h-3.5 shrink-0" />
              {supplier.canonical_website}
            </a>
          )}
          {supplier.canonical_address && (
            <span className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{supplier.canonical_address}</span>
            </span>
          )}
        </div>

        {/* Sanction flag */}
        {supplier.sanction_flag && (
          <div className="flex items-center gap-1.5 text-red-600 text-sm font-medium">
            <AlertTriangle className="w-4 h-4" />
            В списке санкций OFAC
          </div>
        )}

        {/* Source badges */}
        <div className="flex flex-wrap gap-1.5">
          {supplier.evidence.map(e => (
            <a
              key={e.source_url}
              href={e.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-2 py-0.5 rounded transition-colors"
            >
              {ADAPTER_LABELS[e.adapter] ?? e.adapter}
            </a>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={() => setOpen(v => !v)}
            className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
          >
            {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            {open ? "Скрыть" : "Доказательства"}
          </button>
          <Link
            href={`/suppliers/${supplier.cluster_id}`}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Полный профиль
          </Link>
        </div>
      </div>

      {/* Evidence panel */}
      {open && (
        <div className="border-t bg-gray-50 divide-y divide-gray-100">
          {supplier.evidence.map((e, i) => (
            <div key={i} className="px-5 py-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-700">
                  {ADAPTER_LABELS[e.adapter] ?? e.adapter}
                </span>
                <a
                  href={e.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                >
                  Открыть <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              {e.matched_fields.length > 0 && (
                <p className="text-xs text-gray-500">
                  Совпало: {e.matched_fields.join(", ")}
                </p>
              )}
              {e.snippet && (
                <p className="text-xs text-gray-600 line-clamp-2">{e.snippet}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
