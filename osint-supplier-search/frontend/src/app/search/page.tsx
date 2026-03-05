"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Search, Loader2 } from "lucide-react";
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

const schema = z.object({
  query: z.string().min(1, "Введите название товара").max(500),
  countries: z.array(z.string()).default([]),
  supplier_types: z.array(z.string()).default([]),
});

type FormValues = z.infer<typeof schema>;

export default function SearchPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, control, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { query: "", countries: [], supplier_types: [] },
  });

  async function onSubmit(values: FormValues) {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("Необходима авторизация");
        return;
      }
      const { job_id } = await createSearch(
        values.query,
        { countries: values.countries, supplier_types: values.supplier_types, adapters: [] },
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
