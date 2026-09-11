<script lang="ts">
	/**
	 * Left-panel object tree: add objects, select, rename inline, toggle
	 * visibility/lock, delete. Composition title editable at the top.
	 */
	import { shotStore } from '$lib/shot/shotStore.svelte';
	import type { ObjectType } from '$lib/shot/shotStore.svelte';

	const ADD_TYPES: { type: ObjectType; label: string; group: string }[] = [
		{ type: 'male', label: 'Male', group: 'Characters' },
		{ type: 'female', label: 'Female', group: 'Characters' },
		{ type: 'child', label: 'Child', group: 'Characters' },
		{ type: 'cube', label: 'Cube', group: 'Blockout' },
		{ type: 'plane', label: 'Plane', group: 'Blockout' },
		{ type: 'cylinder', label: 'Cylinder', group: 'Blockout' },
		{ type: 'sphere', label: 'Sphere', group: 'Blockout' },
		{ type: 'capsule', label: 'Capsule', group: 'Blockout' },
		{ type: 'cone', label: 'Cone', group: 'Blockout' },
		{ type: 'torus', label: 'Torus', group: 'Blockout' },
		{ type: 'camera', label: 'Camera', group: 'Blockout' },
	];

	let renamingId = $state<string | null>(null);
	let renameValue = $state('');

	function startRename(id: string, current: string) {
		renamingId = id;
		renameValue = current;
	}

	function commitRename(id: string) {
		const name = renameValue.trim();
		if (name) shotStore.renameObject(id, name);
		renamingId = null;
	}

	let showAdd = $state(false);
</script>

<div class="panel">
	<header class="panel-head">
		<span class="panel-title">Scene</span>
		<div class="head-actions">
			<button class="btn ghost" onclick={() => (showAdd = !showAdd)} title="Add object">＋</button>
			<button
				class="btn ghost danger"
				onclick={() => shotStore.objects.length && shotStore.clearScene()}
				title="Clear scene"
			>⌫</button>
		</div>
	</header>

	{#if showAdd}
		<div class="add-grid">
			{#each ADD_TYPES as t (t.type)}
				<button class="add-item" onclick={() => { shotStore.addObject(t.type); showAdd = false; }}>
					{t.label}
				</button>
			{/each}
		</div>
	{/if}

	<ul class="objects">
		{#each shotStore.objects as o (o.id)}
			<li
				class="row"
				class:selected={o.id === shotStore.selectedObjectId}
			>
				{#if renamingId === o.id}
					<input
						class="rename"
						bind:value={renameValue}
						onkeydown={(e) => e.key === 'Enter' && commitRename(o.id)}
						onblur={() => commitRename(o.id)}
					/>
				{:else}
					<button class="name" onclick={() => shotStore.selectObject(o.id)} ondblclick={() => startRename(o.id, o.name)}>
						<span class="kind">{o.type}</span>
						{o.name}
					</button>
				{/if}
				<div class="row-actions">
					<button class="icon" onclick={() => shotStore.toggleObjectVisibility(o.id)} title="Visibility">
						{o.visible ? '◉' : '○'}
					</button>
					<button class="icon" onclick={() => shotStore.toggleObjectLock(o.id)} title="Lock">
						{o.locked ? '🔒' : '🔓'}
					</button>
					<button class="icon danger" onclick={() => shotStore.deleteObject(o.id)} title="Delete">✕</button>
				</div>
			</li>
		{:else}
			<li class="empty">Empty scene — add a character or blockout shape.</li>
		{/each}
	</ul>

	<footer class="hint">Click selects · drag gizmo moves · double-click renames</footer>
</div>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}
	.panel-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 12px 8px;
	}
	.panel-title {
		font-size: 12px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		opacity: 0.7;
	}
	.head-actions {
		display: flex;
		gap: 4px;
	}
	.btn {
		border: 1px solid var(--border, #2a2f3a);
		background: transparent;
		color: inherit;
		border-radius: 6px;
		padding: 2px 8px;
		cursor: pointer;
		font-size: 13px;
		line-height: 1.4;
	}
	.btn:hover {
		background: rgba(255, 255, 255, 0.06);
	}
	.danger {
		color: #e5697a;
	}
	.add-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 6px;
		padding: 0 12px 10px;
	}
	.add-item {
		border: 1px solid var(--border, #2a2f3a);
		background: transparent;
		color: inherit;
		border-radius: 6px;
		padding: 6px 4px;
		font-size: 12px;
		cursor: pointer;
	}
	.add-item:hover {
		background: rgba(255, 255, 255, 0.06);
	}
	.objects {
		flex: 1;
		overflow-y: auto;
		list-style: none;
		margin: 0;
		padding: 0 6px;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 4px;
		border-radius: 6px;
		padding: 2px 4px;
	}
	.row:hover {
		background: rgba(255, 255, 255, 0.04);
	}
	.row.selected {
		background: rgba(99, 102, 241, 0.22);
	}
	.name {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 8px;
		background: none;
		border: 0;
		color: inherit;
		text-align: left;
		padding: 6px 6px;
		cursor: pointer;
		font-size: 13px;
	}
	.kind {
		font-size: 10px;
		text-transform: uppercase;
		opacity: 0.55;
		min-width: 44px;
	}
	.row-actions {
		display: none;
		gap: 2px;
	}
	.row:hover .row-actions,
	.row.selected .row-actions {
		display: flex;
	}
	.icon {
		background: none;
		border: 0;
		color: inherit;
		opacity: 0.7;
		cursor: pointer;
		font-size: 12px;
		padding: 2px 4px;
	}
	.icon:hover {
		opacity: 1;
	}
	.rename {
		flex: 1;
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid var(--border, #2a2f3a);
		color: inherit;
		border-radius: 4px;
		padding: 4px 6px;
		font-size: 13px;
	}
	.empty {
		padding: 16px 12px;
		font-size: 12px;
		opacity: 0.5;
	}
	.hint {
		padding: 8px 12px;
		font-size: 11px;
		opacity: 0.45;
		border-top: 1px solid var(--border, #232733);
	}
</style>
