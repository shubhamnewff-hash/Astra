import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Trash2, Edit2, X, MessageCircle, Loader2 } from "lucide-react";
import AnswerPreview from "@/components/AnswerPreview";

const EMPTY_FORM = {
  question: "", triggers: [], response: "", buttons: [],
  suggestion_questions: [], active: true,
};

export default function GeneralQuestions() {
  const [items, setItems] = useState([]);
  const [dialog, setDialog] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [newTrigger, setNewTrigger] = useState("");
  const [newButton, setNewButton] = useState({ label: "", action: "" });
  const [newSuggestion, setNewSuggestion] = useState("");
  const [modules, setModules] = useState([]);
  const [kbItems, setKbItems] = useState([]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/general-questions");
      setItems(data);
    } catch {}
  }, []);

  useEffect(() => {
    load();
    api.get("/knowledge/modules").then(({ data }) => setModules(data)).catch(() => {});
    api.get("/knowledge/items").then(({ data }) => setKbItems(data)).catch(() => {});
  }, [load]);

  const openNew = () => { setEditId(null); setForm({ ...EMPTY_FORM }); setDialog(true); };
  const openEdit = (item) => {
    setEditId(item._id);
    setForm({
      question: item.question || "",
      triggers: item.triggers || [],
      response: item.response || "",
      buttons: item.buttons || [],
      suggestion_questions: item.suggestion_questions || [],
      active: item.active !== false,
    });
    setDialog(true);
  };

  const save = async () => {
    if (!form.question.trim() || !form.response.trim()) {
      toast.error("Question and response are required");
      return;
    }
    setSaving(true);
    try {
      if (editId) {
        await api.put(`/admin/general-questions/${editId}`, form);
        toast.success("Updated");
      } else {
        await api.post("/admin/general-questions", form);
        toast.success("Created");
      }
      setDialog(false);
      load();
    } catch { toast.error("Failed to save"); }
    setSaving(false);
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this general question?")) return;
    try { await api.delete(`/admin/general-questions/${id}`); load(); toast.success("Deleted"); } catch {}
  };

  const addTrigger = () => {
    const t = newTrigger.trim();
    if (t && !form.triggers.includes(t)) {
      setForm(p => ({ ...p, triggers: [...p.triggers, t] }));
      setNewTrigger("");
    }
  };

  const addButton = () => {
    if (newButton.label.trim()) {
      setForm(p => ({ ...p, buttons: [...p.buttons, { ...newButton }] }));
      setNewButton({ label: "", action: "" });
    }
  };

  const addSuggestion = () => {
    const s = newSuggestion.trim();
    if (s && !form.suggestion_questions.includes(s)) {
      setForm(p => ({ ...p, suggestion_questions: [...p.suggestion_questions, s] }));
      setNewSuggestion("");
    }
  };

  // Get KB questions for selection
  const availableKbQuestions = kbItems.map(i => i.question || i.title).filter(Boolean);

  return (
    <div className="space-y-6" data-testid="general-questions-page">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: '#0F172A' }}>General Questions</h2>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>
            Configure responses for greetings, casual questions, and non-KB queries (e.g., "hindi aati hai?")
          </p>
        </div>
        <Button onClick={openNew} style={{ background: '#FF6B00' }} className="text-white" data-testid="add-general-q-btn">
          <Plus className="h-4 w-4 mr-1" /> Add General Question
        </Button>
      </div>

      <Card className="border border-[#E2E8F0]">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Question</TableHead>
                <TableHead>Triggers</TableHead>
                <TableHead>Response</TableHead>
                <TableHead>Buttons</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(item => (
                <TableRow key={item._id}>
                  <TableCell className="font-medium" style={{ color: '#0A101D' }}>{item.question}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {(item.triggers || []).slice(0, 3).map((t, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">{t}</Badge>
                      ))}
                      {(item.triggers || []).length > 3 && <Badge variant="secondary" className="text-xs">+{item.triggers.length - 3}</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-[200px] truncate text-sm" style={{ color: '#64748B' }}>
                    {item.response?.slice(0, 60)}...
                  </TableCell>
                  <TableCell>{(item.buttons || []).length}</TableCell>
                  <TableCell>
                    <Badge className={item.active !== false ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}>
                      {item.active !== false ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => openEdit(item)}>
                        <Edit2 className="h-4 w-4 text-blue-500" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => remove(item._id)}>
                        <Trash2 className="h-4 w-4 text-red-400" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12">
                    <MessageCircle className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                    <p className="text-sm" style={{ color: '#64748B' }}>No general questions configured yet</p>
                    <p className="text-xs mt-1" style={{ color: '#94A3B8' }}>Add responses for greetings and casual queries</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Dialog */}
      <Dialog open={dialog} onOpenChange={setDialog}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editId ? "Edit" : "Add"} General Question</DialogTitle>
          </DialogHeader>

          <div className="space-y-5">
            {/* Question */}
            <div>
              <Label>Question / Label</Label>
              <Input value={form.question} onChange={(e) => setForm(p => ({ ...p, question: e.target.value }))}
                placeholder='e.g., "hindi aati hai?" or "Hello" or "Thanks"' className="mt-1.5" />
            </div>

            {/* Triggers */}
            <div>
              <Label>Trigger Phrases <span className="text-xs font-normal text-[#64748B]">(user messages that trigger this response)</span></Label>
              <div className="flex gap-2 mt-1.5">
                <Input value={newTrigger} onChange={(e) => setNewTrigger(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addTrigger()}
                  placeholder='e.g., "hello", "hi", "hindi aati"' className="flex-1" />
                <Button onClick={addTrigger} size="sm" variant="outline">Add</Button>
              </div>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {form.triggers.map((t, i) => (
                  <Badge key={i} variant="secondary" className="gap-1 pr-1">
                    {t}
                    <button onClick={() => setForm(p => ({ ...p, triggers: p.triggers.filter((_, j) => j !== i) }))}
                      className="ml-0.5 rounded-full hover:bg-gray-300 p-0.5"><X className="h-3 w-3" /></button>
                  </Badge>
                ))}
              </div>
            </div>

            {/* Response */}
            <div>
              <Label>Response <span className="text-xs font-normal text-[#64748B]">(supports **bold**, *italic*)</span></Label>
              <Textarea value={form.response} onChange={(e) => setForm(p => ({ ...p, response: e.target.value }))}
                className="mt-1.5 min-h-[100px] font-mono text-sm"
                placeholder='e.g., "Hello! How can I help you today? Here are some things I can assist with:"' />
            </div>

            {/* Buttons */}
            <div>
              <Label>Action Buttons <span className="text-xs font-normal text-[#64748B]">(shown below the response)</span></Label>
              <div className="flex gap-2 mt-1.5">
                <Input value={newButton.label} onChange={(e) => setNewButton(p => ({ ...p, label: e.target.value }))}
                  placeholder="Button label" className="flex-1" />
                <Input value={newButton.action} onChange={(e) => setNewButton(p => ({ ...p, action: e.target.value }))}
                  placeholder="URL or action (optional)" className="flex-1" />
                <Button onClick={addButton} size="sm" variant="outline">Add</Button>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {form.buttons.map((b, i) => (
                  <Badge key={i} className="bg-orange-50 text-[#FF6B00] border border-orange-200 gap-1 pr-1">
                    {b.label} {b.action && <span className="text-xs opacity-60">→ {b.action.slice(0, 20)}</span>}
                    <button onClick={() => setForm(p => ({ ...p, buttons: p.buttons.filter((_, j) => j !== i) }))}
                      className="ml-0.5 rounded-full hover:bg-orange-200 p-0.5"><X className="h-3 w-3" /></button>
                  </Badge>
                ))}
              </div>
            </div>

            {/* Suggestion Questions */}
            <div>
              <Label>Suggestion Questions <span className="text-xs font-normal text-[#64748B]">(KB questions to show alongside this response)</span></Label>
              <div className="flex gap-2 mt-1.5">
                <select className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={newSuggestion} onChange={(e) => setNewSuggestion(e.target.value)}>
                  <option value="">Select a KB question...</option>
                  {availableKbQuestions.filter(q => !form.suggestion_questions.includes(q)).map((q, i) => (
                    <option key={i} value={q}>{q}</option>
                  ))}
                </select>
                <Button onClick={addSuggestion} size="sm" variant="outline">Add</Button>
              </div>
              <div className="space-y-1.5 mt-2">
                {form.suggestion_questions.map((q, i) => (
                  <div key={i} className="flex items-center justify-between bg-gray-50 rounded px-3 py-1.5 text-sm group">
                    <span>{q}</span>
                    <button onClick={() => setForm(p => ({ ...p, suggestion_questions: p.suggestion_questions.filter((_, j) => j !== i) }))}
                      className="opacity-0 group-hover:opacity-100 p-0.5"><X className="h-3.5 w-3.5 text-red-400" /></button>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Toggle */}
            <div className="flex items-center gap-3 pt-2">
              <Switch checked={form.active} onCheckedChange={(v) => setForm(p => ({ ...p, active: v }))} />
              <Label>Active</Label>
            </div>

            <AnswerPreview
              explanation={form.response}
              suggestions={form.suggestion_questions}
              buttons={form.buttons}
              emptyHint="Add a response, buttons or suggestion questions to preview how users will see this answer."
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving} style={{ background: '#FF6B00' }} className="text-white">
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {editId ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
