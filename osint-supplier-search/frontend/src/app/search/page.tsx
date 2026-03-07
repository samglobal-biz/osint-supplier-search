"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Search, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { createSearch } from "@/lib/api";
import { getToken } from "@/lib/supabase";

const COUNTRIES = [
  { value: "US", label: "🇺🇸 США" },
  { value: "DE", label: "🇩🇪 Германия" },
  { value: "CN", label: "🇨🇳 Китай" },
  { value: "TR", label: "🇹🇷 Турция" },
  { value: "IN", label: "🇮🇳 Индия" },
  { value: "GB", label: "🇬🇧 Великобритания" },
  { value: "FR", label: "🇫🇷 Франция" },
  { value: "MX", label: "🇲🇽 Мексика" },
  { value: "BR", label: "🇧🇷 Бразилия" },
  { value: "AE", label: "🇦🇪 ОАЭ" },
  { value: "BE", label: "🇧🇪 Бельгия" },
  { value: "NL", label: "🇳🇱 Нидерланды" },
  { value: "IT", label: "🇮🇹 Италия" },
  { value: "ES", label: "🇪🇸 Испания" },
  { value: "PL", label: "🇵🇱 Польша" },
  { value: "RU", label: "🇷🇺 Россия" },
];

const SUPPLIER_TYPES = [
  { value: "manufacturer", label: "Производитель" },
  { value: "distributor",  label: "Дистрибьютор" },
  { value: "importer",     label: "Импортёр" },
  { value: "exporter",     label: "Экспортёр" },
  { value: "wholesaler",   label: "Оптовый продавец" },
  { value: "trader",       label: "Трейдер" },
];

const ADAPTER_GROUPS = [
  {
    label: "Официальные реестры",
    adapters: [
      { value: "gleif",             label: "GLEIF" },
      { value: "opencorporates",    label: "OpenCorporates" },
      { value: "companies_house_uk",label: "Companies House UK" },
      { value: "wikidata",          label: "Wikidata" },
    ],
  },
  {
    label: "B2B каталоги",
    adapters: [
      { value: "europages",         label: "Europages" },
      { value: "kompass",           label: "Kompass" },
      { value: "directindustry",    label: "DirectIndustry" },
      { value: "thomasnet",         label: "ThomasNet" },
      { value: "tradekey",          label: "TradeKey" },
      { value: "wlw",               label: "WLW (DACH)" },
      { value: "ec21",              label: "EC21" },
      { value: "exporthub",         label: "ExportHub" },
      { value: "go4worldbusiness",  label: "Go4WorldBusiness" },
      { value: "exporters_sg",      label: "Exporters.SG" },
      { value: "exportpages",       label: "ExportPages (EU)" },
      { value: "tradeford",         label: "Tradeford" },
      { value: "hktdc",             label: "HKTDC (HK)" },
    ],
  },
  {
    label: "Азиатские платформы",
    adapters: [
      { value: "alibaba",           label: "Alibaba" },
      { value: "made_in_china",     label: "Made in China" },
      { value: "global_sources",    label: "Global Sources" },
      { value: "indiamart",         label: "IndiaMart" },
      { value: "tradeindia",        label: "TradeIndia" },
      { value: "exporters_india",   label: "Exporters India" },
      { value: "dhgate",            label: "DHgate" },
    ],
  },
  {
    label: "Таможенные данные",
    adapters: [
      { value: "importyeti",        label: "ImportYeti" },
      { value: "volza",             label: "Volza" },
      { value: "tridge",            label: "Tridge" },
    ],
  },
  {
    label: "Региональные каталоги",
    adapters: [
      { value: "yellow_pages_us",   label: "Yellow Pages (США)" },
      { value: "yell_uk",           label: "Yell (UK)" },
      { value: "gelbeseiten",       label: "Gelbe Seiten (DE)" },
      { value: "pagine_gialle",     label: "Pagine Gialle (IT)" },
      { value: "manta",             label: "Manta" },
      { value: "cylex",             label: "Cylex" },
      { value: "b2brazil",          label: "B2Brazil" },
    ],
  },
];

const ALL_ADAPTER_VALUES = ADAPTER_GROUPS.flatMap(g => g.adapters.map(a => a.value));

const schema = z.object({
  query: z.string().min(1, "Введите название товара").max(500),
  countries: z.array(z.string()).default([]),
  supplier_types: z.array(z.string()).default([]),
  adapters: z.array(z.string()).default([]),
});

type FormValues = z.infer<typeof schema>;

export default function SearchPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adaptersOpen, setAdaptersOpen] = useState(false);

  const { register, handleSubmit, control, watch, setValue, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { query: "", countries: [], supplier_types: [], adapters: [] },
  });

  const selectedAdapters = watch("adapters");
  const allSelected = selectedAdapters.length === 0 || selectedAdapters.length === ALL_ADAPTER_VALUES.length;

  function toggleAdapter(value: string) {
    // Start from "all selected" state if nothing explicitly chosen yet
    const current = selectedAdapters.length === 0 ? ALL_ADAPTER_VALUES : selectedAdapters;
    const next = current.includes(value) ? current.filter(v => v !== value) : [...current, value];
    // If all selected again, collapse back to [] (= all)
    setValue("adapters", next.length === ALL_ADAPTER_VALUES.length ? [] : next);
  }

  function toggleGroup(groupAdapters: string[]) {
    const current = selectedAdapters.length === 0 ? ALL_ADAPTER_VALUES : selectedAdapters;
    const allGroupSelected = groupAdapters.every(v => current.includes(v));
    const next = allGroupSelected
      ? current.filter(v => !groupAdapters.includes(v))
      : [...new Set([...current, ...groupAdapters])];
    setValue("adapters", next.length === ALL_ADAPTER_VALUES.length ? [] : next);
  }

  function isAdapterSelected(value: string) {
    return selectedAdapters.length === 0 || selectedAdapters.includes(value);
  }

  async function onSubmit(values: FormValues) {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) { router.push("/login"); return; }
      const { job_id } = await createSearch(
        values.query,
        { countries: values.countries, supplier_types: values.supplier_types, adapters: values.adapters },
        token,
      );
      router.push(`/jobs/${job_id}`);
    } catch (e: any) {
      setError(e?.message ?? "Ошибка при запуске поиска");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="max-w-xl w-full space-y-6">
        <h1 className="text-2xl font-bold">Поиск поставщиков</h1>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {/* Query */}
          <div>
            <label className="block text-sm font-medium mb-1">Название товара</label>
            <input
              {...register("query")}
              placeholder="Corona Extra, стальные трубы, iPhone 15..."
              className="w-full border rounded-lg px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {errors.query && <p className="text-red-500 text-sm mt-1">{errors.query.message}</p>}
          </div>

          {/* Countries */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Страна <span className="text-gray-400 font-normal">(опционально, по умолчанию — весь мир)</span>
            </label>
            <Controller
              name="countries"
              control={control}
              render={({ field }) => (
                <div className="flex flex-wrap gap-2">
                  {COUNTRIES.map(c => (
                    <button
                      key={c.value}
                      type="button"
                      onClick={() => {
                        const cur = field.value;
                        field.onChange(
                          cur.includes(c.value)
                            ? cur.filter(v => v !== c.value)
                            : [...cur, c.value]
                        );
                      }}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        field.value.includes(c.value)
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                      }`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              )}
            />
          </div>

          {/* Supplier types */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Тип поставщика <span className="text-gray-400 font-normal">(по умолчанию — все)</span>
            </label>
            <Controller
              name="supplier_types"
              control={control}
              render={({ field }) => (
                <div className="flex flex-wrap gap-2">
                  {SUPPLIER_TYPES.map(t => (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => {
                        const cur = field.value;
                        field.onChange(
                          cur.includes(t.value)
                            ? cur.filter(v => v !== t.value)
                            : [...cur, t.value]
                        );
                      }}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        field.value.includes(t.value)
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              )}
            />
          </div>

          {/* Adapters */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => setAdaptersOpen(o => !o)}
              className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-sm font-medium text-gray-700"
            >
              <span>
                Источники данных{" "}
                <span className="font-normal text-gray-400">
                  {allSelected ? "все" : `выбрано ${selectedAdapters.length} из ${ALL_ADAPTER_VALUES.length}`}
                </span>
              </span>
              {adaptersOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
            </button>

            {adaptersOpen && (
              <div className="px-4 py-3 space-y-4 border-t border-gray-200">
                {/* Reset button */}
                {!allSelected && (
                  <button
                    type="button"
                    onClick={() => setValue("adapters", [])}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Выбрать все
                  </button>
                )}

                {ADAPTER_GROUPS.map(group => {
                  const groupVals = group.adapters.map(a => a.value);
                  const current = selectedAdapters.length === 0 ? ALL_ADAPTER_VALUES : selectedAdapters;
                  const groupAllOn = groupVals.every(v => current.includes(v));
                  return (
                    <div key={group.label}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{group.label}</span>
                        <button
                          type="button"
                          onClick={() => toggleGroup(groupVals)}
                          className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                        >
                          {groupAllOn ? "снять" : "выбрать"}
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {group.adapters.map(a => (
                          <button
                            key={a.value}
                            type="button"
                            onClick={() => toggleAdapter(a.value)}
                            className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                              isAdapterSelected(a.value)
                                ? "bg-blue-600 text-white border-blue-600"
                                : "bg-white text-gray-500 border-gray-300 hover:border-blue-400"
                            }`}
                          >
                            {a.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
            {loading ? "Запускаем поиск..." : "Найти поставщиков"}
          </button>
        </form>
      </div>
    </main>
  );
}
