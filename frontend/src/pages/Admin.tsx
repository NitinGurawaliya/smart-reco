import { useEffect, useState, type FormEvent } from "react";
import { Plus, Pencil, Trash2, RefreshCw, AlertCircle } from "lucide-react";
import { catalogApi } from "@/api/catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogClose,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { FreeResourceOut, CatalogCreatePayload } from "@/types/api";

const LEVELS = ["beginner", "intermediate", "advanced"];
const CATEGORIES = ["programming", "web-development", "backend", "data", "machine-learning", "computer-science", "devops", "tools", "general"];

const syncBadgeVariant = (s: string) =>
  s === "synced" ? "synced" : s === "failed" ? "failed" : "pending";

interface FormState extends CatalogCreatePayload {
  topic_tags_raw: string;
}

const emptyForm = (): FormState => ({
  title: "", description: "", topic_tags: [], topic_tags_raw: "", youtube_url: "", level: "beginner", category: "programming",
});

export default function Admin() {
  const [items, setItems] = useState<FreeResourceOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<FreeResourceOut | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FreeResourceOut | null>(null);

  const load = () => {
    setLoading(true);
    catalogApi.list().then(setItems).catch(() => setError("Failed to load catalog.")).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditItem(null);
    setForm(emptyForm());
    setFormError("");
    setDialogOpen(true);
  };

  const openEdit = (item: FreeResourceOut) => {
    setEditItem(item);
    setForm({
      title: item.title, description: item.description,
      topic_tags: item.topic_tags, topic_tags_raw: item.topic_tags.join(", "),
      youtube_url: item.youtube_url, level: item.level, category: item.category,
    });
    setFormError("");
    setDialogOpen(true);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError("");
    const payload: CatalogCreatePayload = {
      ...form,
      topic_tags: form.topic_tags_raw.split(",").map((t) => t.trim()).filter(Boolean),
    };
    try {
      if (editItem) {
        const updated = await catalogApi.update(editItem.id, payload);
        setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
      } else {
        const created = await catalogApi.create(payload);
        setItems((prev) => [created, ...prev]);
      }
      setDialogOpen(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await catalogApi.delete(deleteTarget.id);
      setItems((prev) => prev.filter((i) => i.id !== deleteTarget.id));
    } catch {
      setError("Delete failed.");
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleResync = async (item: FreeResourceOut) => {
    try {
      const updated = await catalogApi.resync(item.id);
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
    } catch {
      setError("Resync failed.");
    }
  };

  const setField = (key: keyof FormState, val: string) =>
    setForm((f) => ({ ...f, [key]: val }));

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold text-[#0B1F33]">Free Catalog</h1>
          <p className="text-sm text-[#6B7280] mt-1">Manage the free YouTube / docs resources SmartReco recommends.</p>
        </div>
        <Button onClick={openCreate} className="gap-2"><Plus className="h-4 w-4" /> Add resource</Button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="py-16 text-center text-[#6B7280] border border-dashed border-[#D1CAB8] rounded-xl">
          <p className="text-lg font-medium mb-2">Catalog is empty</p>
          <Button onClick={openCreate} variant="outline" className="gap-1.5"><Plus className="h-4 w-4" /> Add first resource</Button>
        </div>
      ) : (
        <div className="border border-[#D1CAB8] rounded-xl overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#F7F4EF] border-b border-[#D1CAB8]">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-[#6B7280]">Title</th>
                <th className="text-left px-4 py-3 font-medium text-[#6B7280] hidden md:table-cell">Category</th>
                <th className="text-left px-4 py-3 font-medium text-[#6B7280] hidden md:table-cell">Level</th>
                <th className="text-left px-4 py-3 font-medium text-[#6B7280]">Status</th>
                <th className="text-right px-4 py-3 font-medium text-[#6B7280]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.id} className={i < items.length - 1 ? "border-b border-[#D1CAB8]" : ""}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-[#0B1F33] line-clamp-1">{item.title}</div>
                    <div className="text-xs text-[#6B7280] line-clamp-1">{item.description}</div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-[#6B7280]">{item.category}</td>
                  <td className="px-4 py-3 hidden md:table-cell text-[#6B7280]">{item.level}</td>
                  <td className="px-4 py-3">
                    <Badge variant={syncBadgeVariant(item.sync_status)}>{item.sync_status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {item.sync_status === "failed" && (
                        <Button size="sm" variant="default" onClick={() => handleResync(item)} className="gap-1 text-xs">
                          <RefreshCw className="h-3 w-3" /> Resync
                        </Button>
                      )}
                      {item.sync_status !== "failed" && (
                        <Button size="icon" variant="ghost" onClick={() => handleResync(item)} title="Resync">
                          <RefreshCw className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      <Button size="icon" variant="ghost" onClick={() => openEdit(item)}><Pencil className="h-3.5 w-3.5" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => setDeleteTarget(item)} className="text-red-500 hover:text-red-700 hover:bg-red-50">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editItem ? "Edit resource" : "Add free resource"}</DialogTitle>
            <DialogDescription>Fill in the details for this free YouTube / documentation resource.</DialogDescription>
          </DialogHeader>

          {formError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-2">{formError}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="f-title">Title</Label>
              <Input id="f-title" value={form.title} onChange={(e) => setField("title", e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="f-desc">Description</Label>
              <textarea
                id="f-desc"
                rows={3}
                value={form.description}
                onChange={(e) => setField("description", e.target.value)}
                required
                className="flex w-full rounded border border-[#D1CAB8] bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0F8B8D] focus:ring-offset-1 resize-none"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="f-tags">Topic tags <span className="text-[#9CA3AF] font-normal">(comma-separated)</span></Label>
              <Input id="f-tags" value={form.topic_tags_raw} onChange={(e) => setField("topic_tags_raw", e.target.value)} placeholder="python, fastapi, async" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="f-url">YouTube URL</Label>
              <Input id="f-url" type="url" value={form.youtube_url} onChange={(e) => setField("youtube_url", e.target.value)} required placeholder="https://youtube.com/..." />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Level</Label>
                <Select value={form.level} onValueChange={(v) => setField("level", v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {LEVELS.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Category</Label>
                <Select value={form.category} onValueChange={(v) => setField("category", v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <DialogClose asChild>
                <Button type="button" variant="outline">Cancel</Button>
              </DialogClose>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Saving…" : editItem ? "Save changes" : "Add resource"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirm dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete resource?</DialogTitle>
            <DialogDescription>
              This will permanently remove &ldquo;{deleteTarget?.title}&rdquo; from the catalog. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
