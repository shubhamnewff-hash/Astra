import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Save, Loader2, Plus, X, Shuffle, List, CheckSquare, AlertTriangle } from "lucide-react";

export default function AIConfig() {
  const [config, setConfig] = useState({
    provider: "openai", model: "gpt-5.2", api_key: "", system_prompt: "",
    fallback_message: "", fallback_button_text: "", fallback_button_link: "", show_raise_ticket: true,
    enable_suggestions: true, max_suggestions: 3, suggestion_message: "",
    suggested_questions: [], random_suggestions: true, suggestion_modules: [], multilingual: true, max_user_conversations: 25,
    use_ai_router: true, scope_fallback_message: "", enabled_module_labels: [],
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newQuestion, setNewQuestion] = useState("");
  const [modules, setModules] = useState([]);
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    api.get("/admin/ai-config")
      .then(({ data }) => setConfig({
        provider: data.provider || "openai",
        model: data.model || "gpt-5.2",
        api_key: data.api_key || "",
        system_prompt: data.system_prompt || "",
        fallback_message: data.fallback_message || "",
        fallback_button_text: data.fallback_button_text || "Raise Support Ticket",
        fallback_button_link: data.fallback_button_link || "",
        show_raise_ticket: data.show_raise_ticket !== false,
        enable_suggestions: data.enable_suggestions !== false,
        max_suggestions: data.max_suggestions || 3,
        suggestion_message: data.suggestion_message || "I found some related topics. Did you mean one of these?",
        suggested_questions: data.suggested_questions || [],
        random_suggestions: data.random_suggestions !== false,
        suggestion_modules: data.suggestion_modules || [],
        multilingual: data.multilingual !== false,
        max_user_conversations: data.max_user_conversations || 25,
        use_ai_router: data.use_ai_router !== false,
        scope_fallback_message: data.scope_fallback_message || "",
        enabled_module_labels: data.enabled_module_labels || [],
      }));
    api.get("/knowledge/modules").then(({ data }) => setModules(data)).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try { await api.put("/admin/ai-config", config); setSaved(true); setTimeout(() => setSaved(false), 2000); } catch {}
    setSaving(false);
  };

  const addQuestion = () => {
    const q = newQuestion.trim();
    if (q && !config.suggested_questions.includes(q)) {
      setConfig(p => ({ ...p, suggested_questions: [...p.suggested_questions, q] }));
      setNewQuestion("");
    }
  };

  const toggleModule = (modId) => {
    setConfig(p => {
      const current = p.suggestion_modules || [];
      return {
        ...p,
        suggestion_modules: current.includes(modId)
          ? current.filter(id => id !== modId)
          : [...current, modId],
      };
    });
  };

  const resetData = async () => {
    setResetting(true);
    try {
      const { data } = await api.post("/admin/reset-data");
      const d = data.deleted || {};
      toast.success(`Reset complete: ${d.conversations || 0} conversations, ${d.messages || 0} messages, ${d.feedback || 0} feedback, ${d.tickets || 0} tickets, ${d.unanswered_questions || 0} unanswered`);
    } catch (e) {
      toast.error("Failed to reset data");
    }
    setResetting(false);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold" style={{ color: '#0F172A' }}>AI Configuration</h2>
        <p className="text-sm mt-1" style={{ color: '#64748B' }}>Strictly accurate mode — zero hallucination, KB answers only</p>
      </div>

      {/* AI Provider */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">AI Provider</CardTitle>
          <CardDescription>LLM for generating responses from KB context</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div>
              <Label>Provider</Label>
              <select className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm mt-1.5"
                value={config.provider} onChange={(e) => setConfig(p => ({ ...p, provider: e.target.value }))}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
              </select>
            </div>
            <div><Label>Model</Label><Input value={config.model} className="mt-1.5" onChange={(e) => setConfig(p => ({ ...p, model: e.target.value }))} /></div>
            <div><Label>API Key</Label><Input type="password" value={config.api_key} className="mt-1.5" onChange={(e) => setConfig(p => ({ ...p, api_key: e.target.value }))} /></div>
          </div>
          <div className="mt-4"><Label>Custom System Prompt (optional)</Label><Textarea value={config.system_prompt} onChange={(e) => setConfig(p => ({ ...p, system_prompt: e.target.value }))} className="mt-1.5 min-h-[80px]" placeholder="Optional custom instructions..." /></div>
        </CardContent>
      </Card>

      {/* Smart Suggestions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Smart Suggestions</CardTitle>
          <CardDescription>When AI is unsure, it shows closest matching KB questions. Configure which modules to suggest from.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <Label className="mb-2 block">Suggestion Message</Label>
              <Textarea value={config.suggestion_message}
                onChange={(e) => setConfig(p => ({ ...p, suggestion_message: e.target.value }))}
                placeholder="I found some related topics. Did you mean one of these?"
                className="min-h-[60px]" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="flex items-center gap-3">
                <Switch checked={config.enable_suggestions}
                  onCheckedChange={(v) => setConfig(p => ({ ...p, enable_suggestions: v }))} />
                <Label>Enable suggestions</Label>
              </div>
              <div>
                <Label>Max Suggestions (1-5)</Label>
                <Input type="number" min={1} max={5} value={config.max_suggestions}
                  onChange={(e) => setConfig(p => ({ ...p, max_suggestions: parseInt(e.target.value) || 3 }))}
                  className="mt-1.5 w-24" />
              </div>
              <div className="flex items-center gap-3" data-testid="multilingual-toggle">
                <Switch checked={config.multilingual}
                  onCheckedChange={(v) => setConfig(p => ({ ...p, multilingual: v }))} />
                <div>
                  <Label>Multilingual (auto-translate)</Label>
                  <p className="text-xs" style={{ color: '#64748B' }}>Detect user language and respond in it</p>
                </div>
              </div>
            </div>

            {/* Module Filter for Suggestions */}
            {modules.length > 0 && (
              <div className="pt-3 border-t">
                <Label className="mb-2 block flex items-center gap-1.5">
                  <CheckSquare className="h-4 w-4" style={{ color: '#FF6B00' }} />
                  Suggestion Source Modules
                </Label>
                <p className="text-xs mb-3" style={{ color: '#64748B' }}>
                  Select which modules' questions appear as suggestions. Leave all unchecked to include all modules.
                </p>
                <div className="flex flex-wrap gap-2">
                  {modules.map(mod => (
                    <button key={mod._id} type="button"
                      className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${
                        (config.suggestion_modules || []).includes(mod._id)
                          ? 'border-[#FF6B00] bg-orange-50 text-[#FF6B00] font-medium'
                          : 'border-gray-200 text-gray-500 hover:border-gray-300'
                      }`}
                      onClick={() => toggleModule(mod._id)}>
                      {mod.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Home Screen Questions */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <List className="h-5 w-5" style={{ color: '#FF6B00' }} />
            <CardTitle className="text-lg">Home Screen Questions</CardTitle>
          </div>
          <CardDescription>Questions shown on chat home screen</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center gap-3 pb-3 border-b">
              <Switch checked={config.random_suggestions}
                onCheckedChange={(v) => setConfig(p => ({ ...p, random_suggestions: v }))} />
              <div>
                <Label className="flex items-center gap-1.5"><Shuffle className="h-3.5 w-3.5" /> Random from KB</Label>
                <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>
                  {config.random_suggestions ? "Random questions from KB for each user" : "Fixed questions from list below"}
                </p>
              </div>
            </div>
            {!config.random_suggestions && (
              <>
                <div className="flex gap-2">
                  <Input placeholder="Type a suggested question..." value={newQuestion}
                    onChange={(e) => setNewQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addQuestion()} className="flex-1" />
                  <Button onClick={addQuestion} size="sm" style={{ background: '#FF6B00' }} className="text-white">
                    <Plus className="h-4 w-4 mr-1" /> Add
                  </Button>
                </div>
                <div className="space-y-2">
                  {config.suggested_questions.length === 0 && (
                    <p className="text-sm py-4 text-center" style={{ color: '#94A3B8' }}>No custom questions. Add above or enable random.</p>
                  )}
                  {config.suggested_questions.map((q, i) => (
                    <div key={i} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 group">
                      <span className="text-sm" style={{ color: '#334155' }}>{q}</span>
                      <button onClick={() => setConfig(p => ({ ...p, suggested_questions: p.suggested_questions.filter((_, j) => j !== i) }))}
                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-50">
                        <X className="h-4 w-4 text-red-400" />
                      </button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Fallback */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Fallback Behavior</CardTitle>
          <CardDescription>When no answer is found</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="md:col-span-2"><Label>Default Fallback Message</Label><Textarea value={config.fallback_message} onChange={(e) => setConfig(p => ({ ...p, fallback_message: e.target.value }))} className="mt-1.5 min-h-[60px]" data-testid="default-fallback-input" /><p className="text-xs mt-1.5" style={{ color: '#64748B' }}>Shown when AI can't find an answer within a topic it IS trained on.</p></div>
            <div className="md:col-span-2">
              <Label>Out-of-Scope Fallback Message <span className="text-xs font-normal" style={{ color: '#94A3B8' }}>(shown when user asks about untrained topics)</span></Label>
              <Textarea value={config.scope_fallback_message}
                onChange={(e) => setConfig(p => ({ ...p, scope_fallback_message: e.target.value }))}
                className="mt-1.5 min-h-[60px]" data-testid="scope-fallback-input"
                placeholder="I'm currently trained only on: {modules}. Please ask about these topics." />
              <p className="text-xs mt-1.5" style={{ color: '#64748B' }}>Use <code className="text-[#FF6B00]">{"{modules}"}</code> to auto-insert your trained module list. Leave blank to use the default fallback.</p>
            </div>
            <div className="md:col-span-2">
              <Label>Trained Modules <span className="text-xs font-normal" style={{ color: '#94A3B8' }}>(comma-separated labels for the out-of-scope message)</span></Label>
              <Input value={(config.enabled_module_labels || []).join(", ")}
                onChange={(e) => setConfig(p => ({ ...p, enabled_module_labels: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }))}
                className="mt-1.5" data-testid="enabled-modules-input"
                placeholder="e.g., Sales Invoices, GST, Recovery Management" />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={config.show_raise_ticket}
                onCheckedChange={(v) => setConfig(p => ({ ...p, show_raise_ticket: v }))} />
              <Label>Show "Raise Ticket" button</Label>
            </div>
            <div><Label>Ticket Button Text</Label><Input value={config.fallback_button_text} onChange={(e) => setConfig(p => ({ ...p, fallback_button_text: e.target.value }))} className="mt-1.5" /></div>
            <div><Label>Ticket Button Link</Label><Input value={config.fallback_button_link} onChange={(e) => setConfig(p => ({ ...p, fallback_button_link: e.target.value }))} className="mt-1.5" placeholder="https://..." /></div>
          </div>
        </CardContent>
      </Card>

      {/* AI Router */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">AI Semantic Router</CardTitle>
          <CardDescription>Smarter context-aware suggestions powered by gpt-5.2 (recommended)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3" data-testid="ai-router-toggle">
            <Switch checked={config.use_ai_router}
              onCheckedChange={(v) => setConfig(p => ({ ...p, use_ai_router: v }))} />
            <div>
              <Label>Enable AI semantic router</Label>
              <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>
                Uses the LLM to understand user intent — picks the best KB items even when keywords don't overlap
                (e.g., "dynamic qr" → "Amount-Based QR"). Falls back to keyword matching if the LLM fails.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3 pt-2">
        <Button onClick={save} disabled={saving} style={{ background: '#FF6B00' }} className="text-white px-8" data-testid="save-ai-config-top">
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
          {saved ? "Saved!" : "Save Configuration"}
        </Button>
        {saved && <span className="text-sm text-green-600 font-medium">Saved successfully</span>}
      </div>

      {/* User Experience */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">User Experience</CardTitle>
          <CardDescription>How users see their conversation history</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <Label>Conversations visible per user (latest N)</Label>
              <Input type="number" min={5} max={500} value={config.max_user_conversations}
                onChange={(e) => setConfig(p => ({ ...p, max_user_conversations: parseInt(e.target.value) || 25 }))}
                className="mt-1.5 w-32" data-testid="max-conversations-input" />
              <p className="text-xs mt-1.5" style={{ color: '#64748B' }}>
                Older conversations beyond this limit are auto-deleted to keep the sidebar clean. Default: 25.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3 pt-2">
        <Button onClick={save} disabled={saving} style={{ background: '#FF6B00' }} className="text-white px-8" data-testid="save-ai-config">
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
          {saved ? "Saved!" : "Save Configuration"}
        </Button>
        {saved && <span className="text-sm text-green-600 font-medium">Saved successfully</span>}
      </div>

      {/* Danger Zone */}
      <Card className="border-red-200 bg-red-50/30">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2 text-red-700">
            <AlertTriangle className="h-5 w-5" /> Danger Zone
          </CardTitle>
          <CardDescription className="text-red-600/80">
            Wipe all transactional data (conversations, messages, feedback, tickets, unanswered questions) to start with clean real data.
            Knowledge Base, users, and configuration are preserved.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" data-testid="reset-data-button" disabled={resetting}>
                {resetting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <AlertTriangle className="h-4 w-4 mr-2" />}
                Reset All Data
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Reset all transactional data?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently deletes ALL conversations, messages, feedback, tickets, and unanswered questions across every user.
                  Knowledge Base, users, and configuration are kept intact. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={resetData} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-reset-data">
                  Yes, Reset Everything
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </div>
  );
}
