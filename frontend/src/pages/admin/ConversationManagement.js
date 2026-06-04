import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Check, X, MessageSquare, Clock, CheckCircle, AlertTriangle, Eye, Shield, Brain, Sparkles, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";

const STATUS_BADGE = {
  pending: { label: "Pending", color: "#F59E0B", icon: Clock },
  reviewed: { label: "Reviewed", color: "#10B981", icon: CheckCircle },
  flagged: { label: "Flagged", color: "#EF4444", icon: AlertTriangle },
};

function ConfidenceBadge({ msg }) {
  if (msg.role !== "assistant") return null;
  const confidence = msg.confidence;
  const label = msg.confidence_label;
  const source = msg.source;

  if (confidence === undefined && !source) return null;

  let color, bg, icon, text;
  if (source === "trained_answer") {
    color = "#10B981"; bg = "#ECFDF5"; icon = Shield; text = "Trained Answer (100%)";
  } else if (source === "ai_kb") {
    const c = confidence || 0;
    if (c >= 70) { color = "#10B981"; bg = "#ECFDF5"; }
    else if (c >= 40) { color = "#F59E0B"; bg = "#FFFBEB"; }
    else { color = "#EF4444"; bg = "#FEF2F2"; }
    icon = Brain; text = label || `AI from KB (${c}%)`;
  } else if (source === "suggestion" || source === "ai_uncertain") {
    color = "#F59E0B"; bg = "#FFFBEB"; icon = Sparkles; text = label || "Suggestions Shown";
  } else if (source === "fallback" || source === "ai_fallback") {
    color = "#EF4444"; bg = "#FEF2F2"; icon = AlertTriangle; text = label || "Fallback (No Match)";
  } else {
    return null;
  }

  const Icon = icon;
  return (
    <div data-testid="confidence-badge" className="flex items-center gap-1.5 mt-1.5 px-2 py-1 rounded-md text-xs font-medium" style={{ color, background: bg }}>
      <Icon className="h-3 w-3" />
      <span>{text}</span>
      {confidence !== undefined && (
        <div className="ml-auto w-16 h-1.5 rounded-full bg-gray-200 overflow-hidden">
          <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(confidence, 100)}%`, background: color }} />
        </div>
      )}
    </div>
  );
}

export default function ConversationManagement() {
  const [conversations, setConversations] = useState([]);
  const [tab, setTab] = useState("all");
  const [viewDialog, setViewDialog] = useState(null);
  const [viewMessages, setViewMessages] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/conversations");
      setConversations(data);
      setSelected(new Set());
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleReview = async (id, status) => {
    try {
      await api.put(`/admin/conversations/${id}/review`, { review_status: status });
      load();
      toast.success(`Conversation ${status}`);
    } catch { toast.error("Failed to update"); }
  };

  const deleteOne = async (id) => {
    if (!window.confirm("Delete this conversation and all its messages?")) return;
    try {
      await api.delete(`/admin/conversations/${id}`);
      toast.success("Conversation deleted");
      load();
    } catch { toast.error("Failed to delete"); }
  };

  const bulkDelete = async () => {
    if (selected.size === 0) return;
    setBulkDeleting(true);
    try {
      const { data } = await api.post("/admin/conversations/bulk-delete", { ids: Array.from(selected) });
      toast.success(`Deleted ${data.deleted_conversations} conversations (${data.deleted_messages} messages, ${data.deleted_feedback} feedback)`);
      load();
    } catch {
      toast.error("Bulk delete failed");
    }
    setBulkDeleting(false);
  };

  const viewConversation = async (conv) => {
    try {
      const { data } = await api.get(`/admin/conversations/${conv._id}/messages`);
      setViewMessages(data.messages);
      setViewDialog(conv);
    } catch { toast.error("Failed to load messages"); }
  };

  const filtered = tab === "all" ? conversations : conversations.filter((c) => (c.review_status || "pending") === tab);

  const toggleOne = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    const visibleIds = filtered.map(c => c._id);
    const allSelected = visibleIds.every(id => selected.has(id));
    setSelected(prev => {
      const next = new Set(prev);
      if (allSelected) visibleIds.forEach(id => next.delete(id));
      else visibleIds.forEach(id => next.add(id));
      return next;
    });
  };

  const allChecked = filtered.length > 0 && filtered.every(c => selected.has(c._id));

  const counts = {
    all: conversations.length,
    pending: conversations.filter((c) => (c.review_status || "pending") === "pending").length,
    reviewed: conversations.filter((c) => c.review_status === "reviewed").length,
    flagged: conversations.filter((c) => c.review_status === "flagged").length,
  };

  return (
    <div className="space-y-6" data-testid="conversation-management">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Conversations</h1>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>
            Showing latest 100 conversations · Review AI confidence levels and bulk-delete from here.
          </p>
        </div>
        <div className="flex gap-2">
          {Object.entries(STATUS_BADGE).map(([key, { label, color }]) => (
            <Badge key={key} variant="outline" className="gap-1.5 px-3 py-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: color }} /> {counts[key]} {label}
            </Badge>
          ))}
        </div>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center justify-between bg-[#FFF7ED] border border-[#FED7AA] rounded-lg px-4 py-2.5" data-testid="bulk-actions-bar">
          <span className="text-sm font-medium text-[#9A3412]">{selected.size} conversation{selected.size > 1 ? "s" : ""} selected</span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())} data-testid="bulk-clear">
              Clear
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={bulkDeleting} data-testid="bulk-delete-button">
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete Selected
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete {selected.size} conversation{selected.size > 1 ? "s" : ""}?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This permanently deletes the selected conversations along with all their messages and feedback. This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={bulkDelete} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-bulk-delete">
                    Yes, Delete {selected.size}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      )}

      <Tabs value={tab} onValueChange={(v) => { setTab(v); setSelected(new Set()); }}>
        <TabsList className="bg-[#F1F5F9]">
          <TabsTrigger value="all" className="data-[state=active]:bg-white">All ({counts.all})</TabsTrigger>
          <TabsTrigger value="pending" className="data-[state=active]:bg-white">Pending ({counts.pending})</TabsTrigger>
          <TabsTrigger value="reviewed" className="data-[state=active]:bg-white">Reviewed ({counts.reviewed})</TabsTrigger>
          <TabsTrigger value="flagged" className="data-[state=active]:bg-white">Flagged ({counts.flagged})</TabsTrigger>
        </TabsList>

        <TabsContent value={tab}>
          <Card className="border border-[#E2E8F0] bg-white">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <MessageSquare className="w-4 h-4 text-[#FF6B00]" /> {filtered.length} Conversations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40px]">
                      <Checkbox checked={allChecked} onCheckedChange={toggleAll} data-testid="select-all-conversations" aria-label="Select all" />
                    </TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Messages</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="w-[170px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((conv) => {
                    const status = STATUS_BADGE[conv.review_status || "pending"] || STATUS_BADGE.pending;
                    return (
                      <TableRow key={conv._id} data-testid={`conv-row-${conv._id}`} data-state={selected.has(conv._id) ? "selected" : undefined}>
                        <TableCell>
                          <Checkbox checked={selected.has(conv._id)} onCheckedChange={() => toggleOne(conv._id)}
                            data-testid={`select-conv-${conv._id}`} aria-label="Select conversation" />
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="text-sm font-medium" style={{ color: '#0A101D' }}>{conv.user_name}</p>
                            <p className="text-xs" style={{ color: '#64748B' }}>{conv.user_email}</p>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate font-medium" style={{ color: '#334155' }}>{conv.title || "New Conversation"}</TableCell>
                        <TableCell><Badge variant="secondary" className="text-xs">{conv.message_count}</Badge></TableCell>
                        <TableCell>
                          <Badge className="text-xs text-white gap-1" style={{ background: status.color }}>
                            {status.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm" style={{ color: '#64748B' }}>
                          {conv.created_at ? new Date(conv.created_at).toLocaleDateString() : "—"}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => viewConversation(conv)}
                              title="View Messages" data-testid={`view-conv-${conv._id}`}>
                              <Eye className="w-4 h-4 text-[#3B82F6]" />
                            </Button>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => handleReview(conv._id, "reviewed")}
                              title="Mark Reviewed" data-testid={`review-conv-${conv._id}`}>
                              <Check className="w-4 h-4 text-[#10B981]" />
                            </Button>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => handleReview(conv._id, "flagged")}
                              title="Flag" data-testid={`flag-conv-${conv._id}`}>
                              <X className="w-4 h-4 text-[#EF4444]" />
                            </Button>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => deleteOne(conv._id)}
                              title="Delete" data-testid={`delete-conv-${conv._id}`}>
                              <Trash2 className="w-4 h-4 text-[#64748B] hover:text-[#EF4444]" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {filtered.length === 0 && (
                    <TableRow><TableCell colSpan={7} className="text-center py-12 text-[#64748B]">
                      <MessageSquare className="w-8 h-8 mx-auto mb-2 text-[#CBD5E1]" />
                      No conversations in this category
                    </TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* View Messages Dialog with Confidence */}
      <Dialog open={!!viewDialog} onOpenChange={() => setViewDialog(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh]" data-testid="conv-messages-dialog">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>
              {viewDialog?.title || "Conversation"} — {viewDialog?.user_name}
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[55vh] pr-2">
            <div className="space-y-3">
              {viewMessages.map((msg, idx) => (
                <div key={msg._id || idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] ${msg.role === "user" ? "" : ""}`}>
                    <div className={`px-4 py-3 rounded-xl text-sm ${
                      msg.role === "user"
                        ? "bg-[#0A101D] text-white rounded-tr-sm"
                        : "bg-[#F8FAFC] border border-[#E2E8F0] rounded-tl-sm"
                    }`} style={msg.role === "assistant" ? { color: '#334155' } : {}}>
                      {msg.role === "assistant" ? (
                        <div className="chat-message-content"><ReactMarkdown>{msg.content}</ReactMarkdown></div>
                      ) : msg.content}
                    </div>
                    {/* Confidence Badge for assistant messages */}
                    <ConfidenceBadge msg={msg} />
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
