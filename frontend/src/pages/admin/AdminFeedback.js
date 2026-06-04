import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { ThumbsUp, ThumbsDown, MessageSquare } from "lucide-react";

export default function AdminFeedback() {
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get("filter") === "not_helpful" ? "not_helpful" :
                     searchParams.get("filter") === "helpful" ? "helpful" : "all";
  const [tab, setTab] = useState(initialTab);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/feedback");
      // Enrich with message + user info
      const enriched = await Promise.all(data.map(async (fb) => {
        let question = "", answer = "", userEmail = "";
        try {
          const { data: msg } = await api.get(`/admin/messages/${fb.message_id}`);
          answer = msg?.content || "";
          question = msg?.user_question || "";
          userEmail = msg?.user_email || "";
        } catch {}
        return { ...fb, question, answer, userEmail };
      }));
      setItems(enriched);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = items.filter(i =>
    tab === "all" ? true :
    tab === "helpful" ? i.is_helpful === true :
    i.is_helpful === false
  );

  const helpfulCount = items.filter(i => i.is_helpful === true).length;
  const notHelpfulCount = items.filter(i => i.is_helpful === false).length;

  return (
    <div className="space-y-6" data-testid="admin-feedback">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>
          User Feedback
        </h1>
        <p className="text-sm mt-1" style={{ color: '#64748B' }}>
          Showing latest 100 feedback entries · Track which AI answers users found helpful to improve KB content.
        </p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-[#F1F5F9]">
          <TabsTrigger value="all" data-testid="feedback-tab-all">All ({items.length})</TabsTrigger>
          <TabsTrigger value="helpful" data-testid="feedback-tab-helpful">
            <ThumbsUp className="w-3.5 h-3.5 mr-1.5" /> Helpful ({helpfulCount})
          </TabsTrigger>
          <TabsTrigger value="not_helpful" data-testid="feedback-tab-not-helpful">
            <ThumbsDown className="w-3.5 h-3.5 mr-1.5" /> Not Helpful ({notHelpfulCount})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={tab} className="mt-4">
          {loading ? (
            <Card className="border border-[#E2E8F0] bg-white">
              <CardContent className="p-12 text-center text-sm" style={{ color: '#64748B' }}>Loading feedback…</CardContent>
            </Card>
          ) : filtered.length === 0 ? (
            <Card className="border border-[#E2E8F0] bg-white">
              <CardContent className="p-12 text-center text-sm" style={{ color: '#64748B' }}>
                <MessageSquare className="w-8 h-8 mx-auto mb-3 opacity-30" />
                No feedback yet for this filter.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {filtered.map(fb => (
                <Card key={fb._id} className="border border-[#E2E8F0] bg-white" data-testid={`feedback-row-${fb._id}`}>
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <Badge variant={fb.is_helpful ? "default" : "destructive"}
                        className={`gap-1.5 ${fb.is_helpful ? 'bg-[#10B981] hover:bg-[#10B981]' : 'bg-[#EF4444] hover:bg-[#EF4444]'} text-white`}>
                        {fb.is_helpful ? <ThumbsUp className="w-3 h-3" /> : <ThumbsDown className="w-3 h-3" />}
                        {fb.is_helpful ? "Helpful" : "Not Helpful"}
                      </Badge>
                      <span className="text-xs" style={{ color: '#64748B' }}>
                        {new Date(fb.created_at).toLocaleString()}
                      </span>
                    </div>
                    {fb.question && (
                      <div className="mb-2">
                        <p className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: '#64748B' }}>User Question</p>
                        <p className="text-sm" style={{ color: '#0A101D' }}>{fb.question}</p>
                      </div>
                    )}
                    {fb.answer && (
                      <div className="mb-2">
                        <p className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: '#64748B' }}>AI Response</p>
                        <p className="text-sm whitespace-pre-wrap line-clamp-3" style={{ color: '#334155' }}>{fb.answer}</p>
                      </div>
                    )}
                    {fb.comment && (
                      <div className="mt-3 p-3 rounded-lg bg-[#FFF7ED] border border-[#FFEDD5]">
                        <p className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: '#FF6B00' }}>User Comment</p>
                        <p className="text-sm" style={{ color: '#0A101D' }}>{fb.comment}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
