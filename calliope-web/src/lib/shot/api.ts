/** Typed fetch helpers for the /api/shots surface. */

export interface Capture {
	id: number;
	composition_id: number;
	kind: 'image' | 'video';
	label: string | null;
	file_path: string | null;
	created_at: string;
}

export const shotApi = {
	async listCaptures(compositionId: number): Promise<Capture[]> {
		const resp = await fetch(`/api/shots/${compositionId}/captures`);
		if (!resp.ok) return [];
		return resp.json();
	},

	async uploadCapture(compositionId: number, dataUrl: string, label: string): Promise<Capture | null> {
		const resp = await fetch(`/api/shots/${compositionId}/captures`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ data_url: dataUrl, label }),
		});
		if (!resp.ok) return null;
		return resp.json();
	},

	async deleteCapture(compositionId: number, captureId: number): Promise<boolean> {
		const resp = await fetch(`/api/shots/${compositionId}/captures/${captureId}`, {
			method: 'DELETE',
		});
		return resp.ok;
	},

	async setCaptureRequest(compositionId: number, label: string): Promise<void> {
		await fetch(`/api/shots/${compositionId}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ capture_request_json: JSON.stringify({ label, source: 'ui' }) }),
		});
	},

	/** Every composition (any session) — used by project pickers to collect captures. */
	async listCompositions(): Promise<Array<{ id: number; agent_session_id: number | null; title: string }>> {
		const resp = await fetch('/api/shots');
		if (!resp.ok) return [];
		return resp.json();
	},

	async deleteComposition(compositionId: number): Promise<boolean> {
		const resp = await fetch(`/api/shots/${compositionId}`, { method: 'DELETE' });
		return resp.ok;
	},
};
