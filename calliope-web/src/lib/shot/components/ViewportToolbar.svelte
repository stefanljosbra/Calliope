<script lang="ts">
	/**
	 * Viewport toolbar pill — Svelte port of open-media's WorkspaceToolbar
	 * (ToolButtons) + ComposerShell topbar actions: gizmo tools (Select /
	 * Move / Rotate / Scale / Pose), undo/redo, grid + composition-guide
	 * toggles, and the capture button. Tool state lives on the shot store;
	 * the two view toggles are local (the viewport owns the grid mesh and
	 * the CSS overlay) and passed up through bindable props.
	 */
	import { shotStore, type ComposerTool } from '../shotStore.svelte';

	let {
		oncapture,
		showGrid = $bindable(true),
		showComposition = $bindable(false),
	}: {
		oncapture?: () => void;
		showGrid?: boolean;
		showComposition?: boolean;
	} = $props();

	const activeTool = $derived(shotStore.activeTool);
	const selected = $derived(shotStore.selectedObject);
	// Pose applies to mannequins only (mirrors the store's canPoseSelection).
	const canPose = $derived(
		!!selected && selected.type !== 'camera' && !['cube', 'plane', 'cylinder', 'sphere', 'capsule', 'cone', 'torus'].includes(selected.type),
	);

	function setTool(tool: ComposerTool) {
		shotStore.setActiveTool(tool);
	}

	const TOOLS = $derived<{ id: ComposerTool; label: string; title: string; disabled?: boolean }[]>([
		{ id: 'select', label: 'Select', title: 'Select (click objects; no gizmo)' },
		{ id: 'move', label: 'Move', title: 'Move (Translate)' },
		{ id: 'rotate', label: 'Rotate', title: 'Rotate' },
		{ id: 'scale', label: 'Scale', title: 'Scale' },
		{ id: 'pose', label: 'Pose', title: canPose ? 'Pose (drag the joint handles)' : 'Pose applies to mannequins only', disabled: !canPose },
	]);
</script>

<div class="toolbar" role="toolbar" aria-label="Viewport tools">
	<div class="group">
		{#each TOOLS as tool (tool.id)}
			<button
				class="btn"
				class:on={activeTool === tool.id}
				disabled={tool.disabled}
				onclick={() => setTool(tool.id)}
				title={tool.title}
			>
				{tool.label}
			</button>
		{/each}
	</div>

	<span class="divider"></span>

	<div class="group">
		<button class="btn" onclick={() => shotStore.undo()} disabled={!shotStore.canUndo} title="Undo last scene change">
			↶
		</button>
		<button class="btn" onclick={() => shotStore.redo()} disabled={!shotStore.canRedo} title="Redo the last undone change">
			↷
		</button>
	</div>

	<span class="divider"></span>

	<div class="group">
		<button class="btn" class:on={showGrid} onclick={() => (showGrid = !showGrid)} title="Toggle grid">
			Grid
		</button>
		<button class="btn" class:on={showComposition} onclick={() => (showComposition = !showComposition)} title="Composition guide (rule of thirds)">
			Composition
		</button>
	</div>

	<span class="divider"></span>

	<button class="btn capture" onclick={() => oncapture?.()} title="Render the current view to a PNG reference">
		◎ Capture
	</button>
</div>

<style>
	.toolbar {
		display: flex;
		align-items: center;
		gap: 6px;
		border: 1px solid var(--border, #2a2f3a);
		background: rgba(16, 18, 24, 0.82);
		border-radius: 999px;
		padding: 4px 8px;
		backdrop-filter: blur(4px);
	}
	.group {
		display: flex;
		align-items: center;
		gap: 2px;
	}
	.divider {
		width: 1px;
		height: 16px;
		background: var(--border, #2a2f3a);
		margin: 0 2px;
	}
	.btn {
		border: 1px solid transparent;
		background: transparent;
		color: inherit;
		border-radius: 999px;
		padding: 3px 9px;
		font-size: 12px;
		font-weight: 500;
		cursor: pointer;
		white-space: nowrap;
		opacity: 0.85;
	}
	.btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.08);
		opacity: 1;
	}
	.btn.on {
		background: rgba(99, 102, 241, 0.25);
		border-color: var(--accent, #6366f1);
		opacity: 1;
	}
	.btn:disabled {
		opacity: 0.35;
		cursor: not-allowed;
	}
	.capture {
		border-color: var(--border, #2a2f3a);
	}
	.capture:hover {
		border-color: var(--accent, #6366f1);
	}
</style>
