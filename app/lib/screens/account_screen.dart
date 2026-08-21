import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// Full-page account screen.
///
/// Profile avatar, account details, screening stats, app info, logout.
class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  String? _phoneNumber;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    final phone = await AuthService().getPhoneNumber();
    if (mounted) {
      setState(() {
        _phoneNumber = phone;
        _loading = false;
      });
    }
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surfaceWhite,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        title: const Text(
          'Log out?',
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: AppTheme.slateInk,
            fontSize: 18,
          ),
        ),
        content: const Text(
          'You will need to verify your mobile number again to log back in.',
          style: TextStyle(color: AppTheme.slateMid, fontSize: 14, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text(
              'Cancel',
              style: TextStyle(color: AppTheme.slateMid),
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.errorRed,
            ),
            child: const Text('Log Out'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      await AuthService().logout();
      if (mounted) {
        Navigator.pushNamedAndRemoveUntil(
          context,
          '/auth/phone',
          (_) => false,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cream,
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppTheme.terracotta),
            )
          : CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                // ── App Bar ────────────────────────────────
                SliverAppBar(
                  pinned: true,
                  backgroundColor: AppTheme.cream,
                  surfaceTintColor: Colors.transparent,
                  scrolledUnderElevation: 0,
                  elevation: 0,
                  leading: IconButton(
                    icon: const Icon(
                      Icons.arrow_back_rounded,
                      color: AppTheme.slateInk,
                    ),
                    onPressed: () => Navigator.pop(context),
                  ),
                  title: const Text(
                    'Account',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.slateInk,
                    ),
                  ),
                  centerTitle: true,
                ),

                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 28),

                        // ── Profile Header ────────────────────
                        Center(
                          child: Column(
                            children: [
                              // Avatar
                              Stack(
                                children: [
                                  Container(
                                    width: 90,
                                    height: 90,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: AppTheme.peach,
                                      border: Border.all(
                                        color: AppTheme.terracotta
                                            .withValues(alpha: 0.25),
                                        width: 3,
                                      ),
                                    ),
                                    child: const Icon(
                                      Icons.person_rounded,
                                      size: 46,
                                      color: AppTheme.terracotta,
                                    ),
                                  ),
                                  // Edit badge
                                  Positioned(
                                    bottom: 2,
                                    right: 2,
                                    child: Container(
                                      width: 26,
                                      height: 26,
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: AppTheme.terracotta,
                                        border: Border.all(
                                          color: AppTheme.cream,
                                          width: 2,
                                        ),
                                      ),
                                      child: const Icon(
                                        Icons.edit_rounded,
                                        size: 12,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 14),

                              const Text(
                                'Research Participant',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w800,
                                  color: AppTheme.slateInk,
                                  letterSpacing: -0.3,
                                ),
                              ),

                              const SizedBox(height: 4),

                              Text(
                                _phoneNumber ?? '—',
                                style: const TextStyle(
                                  fontSize: 14,
                                  color: AppTheme.slateMid,
                                ),
                              ),

                              const SizedBox(height: 12),

                              // Study badge
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 14, vertical: 6),
                                decoration: BoxDecoration(
                                  color: AppTheme.peach,
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(
                                    color: AppTheme.terracotta
                                        .withValues(alpha: 0.2),
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(
                                      Icons.science_outlined,
                                      size: 13,
                                      color: AppTheme.terracottaDark,
                                    ),
                                    const SizedBox(width: 6),
                                    const Text(
                                      'QuadNova Study — Phase 1',
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.terracottaDark,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 32),

                        // ── Stats Row ─────────────────────────
                        Row(
                          children: [
                            Expanded(
                              child: _StatCard(
                                value: '0',
                                label: 'Screenings',
                                icon: Icons.camera_alt_rounded,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _StatCard(
                                value: 'Phase 1',
                                label: 'Study Stage',
                                icon: Icons.biotech_rounded,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _StatCard(
                                value: '—',
                                label: 'Last Scan',
                                icon: Icons.schedule_rounded,
                              ),
                            ),
                          ],
                        ),

                        const SizedBox(height: 28),

                        // ── Account Details ───────────────────
                        _SectionLabel('Account Details'),
                        const SizedBox(height: 10),
                        _InfoCard(
                          children: [
                            _InfoTile(
                              icon: Icons.phone_android_rounded,
                              label: 'Mobile Number',
                              value: _phoneNumber ?? '—',
                            ),
                            const _TileDivider(),
                            _InfoTile(
                              icon: Icons.person_outline_rounded,
                              label: 'Role',
                              value: 'Research Participant',
                            ),
                            const _TileDivider(),
                            _InfoTile(
                              icon: Icons.calendar_today_outlined,
                              label: 'Member Since',
                              value: 'Aug 2026',
                            ),
                          ],
                        ),

                        const SizedBox(height: 24),

                        // ── Study Info ────────────────────────
                        _SectionLabel('Study Information'),
                        const SizedBox(height: 10),
                        _InfoCard(
                          children: [
                            _InfoTile(
                              icon: Icons.science_outlined,
                              label: 'Project',
                              value: 'QuadNova Anaemia Screening',
                            ),
                            const _TileDivider(),
                            _InfoTile(
                              icon: Icons.account_balance_outlined,
                              label: 'Institution',
                              value: 'QuadNova Research Lab',
                            ),
                            const _TileDivider(),
                            _InfoTile(
                              icon: Icons.assignment_outlined,
                              label: 'Phase',
                              value: 'Phase 1 — Prototype',
                            ),
                          ],
                        ),

                        const SizedBox(height: 24),

                        // ── Backend Server ────────────────────
                        _SectionLabel('Backend Server'),
                        const SizedBox(height: 10),
                        _BackendServerCard(),

                        const SizedBox(height: 24),

                        // ── App Info ──────────────────────────
                        _SectionLabel('App'),
                        const SizedBox(height: 10),
                        _InfoCard(
                          children: [
                            _InfoTile(
                              icon: Icons.info_outline_rounded,
                              label: 'Version',
                              value: '1.0.0-beta',
                            ),
                            const _TileDivider(),
                            _InfoTile(
                              icon: Icons.memory_rounded,
                              label: 'AI Model',
                              value: 'MobileNetV3-small',
                            ),
                            const _TileDivider(),
                            _LinkTile(
                              icon: Icons.policy_outlined,
                              label: 'Research Disclaimer',
                              onTap: () {
                                showDialog(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    backgroundColor: AppTheme.surfaceWhite,
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(16)),
                                    title: const Text(
                                      'Research Disclaimer',
                                      style: TextStyle(
                                          fontWeight: FontWeight.w700,
                                          fontSize: 16),
                                    ),
                                    content: const Text(
                                      'HemoScan AI is a research prototype developed '
                                      'by QuadNova. Results are screening estimates '
                                      'only and must not be used for clinical '
                                      'diagnosis. Confirmatory testing by a qualified '
                                      'healthcare professional is always recommended.',
                                      style: TextStyle(
                                          color: AppTheme.slateMid,
                                          fontSize: 14,
                                          height: 1.6),
                                    ),
                                    actions: [
                                      ElevatedButton(
                                        onPressed: () => Navigator.pop(ctx),
                                        child: const Text('Understood'),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                          ],
                        ),

                        const SizedBox(height: 28),

                        // ── Logout Button ─────────────────────
                        SizedBox(
                          width: double.infinity,
                          height: 50,
                          child: OutlinedButton.icon(
                            onPressed: _logout,
                            icon: const Icon(Icons.logout_rounded, size: 18),
                            label: const Text('Log Out'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AppTheme.errorRed,
                              side: BorderSide(
                                color: AppTheme.errorRed.withValues(alpha: 0.4),
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                        ),

                        const SizedBox(height: 40),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

// ── Helper widgets ────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        color: AppTheme.slateLight,
        letterSpacing: 0.8,
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final List<Widget> children;
  const _InfoCard({required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(children: children),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppTheme.terracotta),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.slateMid,
              ),
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.slateInk,
            ),
          ),
        ],
      ),
    );
  }
}

class _LinkTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _LinkTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: const BorderRadius.vertical(bottom: Radius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            Icon(icon, size: 18, color: AppTheme.terracotta),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.slateMid,
                ),
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              size: 18,
              color: AppTheme.slateLight,
            ),
          ],
        ),
      ),
    );
  }
}

class _TileDivider extends StatelessWidget {
  const _TileDivider();

  @override
  Widget build(BuildContext context) {
    return const Divider(
      height: 1,
      indent: 46,
      endIndent: 0,
      color: AppTheme.divider,
    );
  }
}

class _StatCard extends StatelessWidget {
  final String value;
  final String label;
  final IconData icon;

  const _StatCard({
    required this.value,
    required this.label,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        children: [
          Icon(icon, size: 20, color: AppTheme.terracotta),
          const SizedBox(height: 8),
          Text(
            value,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: AppTheme.slateInk,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              color: AppTheme.slateLight,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Backend server card ────────────────────────────────────

class _BackendServerCard extends StatefulWidget {
  @override
  State<_BackendServerCard> createState() => _BackendServerCardState();
}

class _BackendServerCardState extends State<_BackendServerCard> {
  String _url = '';
  bool _checking = false;
  bool? _online;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final url = await ApiService.instance.getBaseUrl();
    if (!mounted) return;
    setState(() => _url = url);
    if (url.isNotEmpty) _ping();
  }

  Future<void> _ping() async {
    setState(() {
      _checking = true;
      _online = null;
    });
    final ok = await ApiService.instance.checkHealth();
    if (mounted) setState(() { _checking = false; _online = ok; });
  }

  @override
  Widget build(BuildContext context) {
    final configured = _url.isNotEmpty;
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceWhite,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.divider),
      ),
      child: Column(
        children: [
          // Status row
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
            child: Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: configured
                        ? (_online == true
                            ? AppTheme.successGreen.withValues(alpha: 0.1)
                            : AppTheme.peach)
                        : AppTheme.surfacePaper,
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: Icon(
                    configured
                        ? (_online == true
                            ? Icons.cloud_done_rounded
                            : Icons.cloud_off_rounded)
                        : Icons.cloud_off_rounded,
                    size: 18,
                    color: configured
                        ? (_online == true
                            ? AppTheme.successGreen
                            : AppTheme.terracotta)
                        : AppTheme.slateLight,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        configured ? 'Server Configured' : 'Not Connected',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.slateInk,
                        ),
                      ),
                      const SizedBox(height: 2),
                      if (_checking)
                        const Text('Checking…',
                            style: TextStyle(
                                fontSize: 11, color: AppTheme.slateLight))
                      else if (configured)
                        Text(
                          _online == true ? 'Online' : (_online == false ? 'Unreachable' : _url),
                          style: TextStyle(
                            fontSize: 11,
                            color: _online == true
                                ? AppTheme.successGreen
                                : AppTheme.slateMid,
                          ),
                          overflow: TextOverflow.ellipsis,
                        )
                      else
                        const Text('Tap to configure',
                            style: TextStyle(
                                fontSize: 11, color: AppTheme.slateLight)),
                    ],
                  ),
                ),
                if (_checking)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: AppTheme.terracotta),
                  )
                else if (configured)
                  GestureDetector(
                    onTap: _ping,
                    child: const Icon(Icons.refresh_rounded,
                        size: 18, color: AppTheme.slateLight),
                  ),
              ],
            ),
          ),
          const Divider(height: 1),
          // Actions
          InkWell(
            onTap: () async {
              await Navigator.pushNamed(context, '/server-setup');
              _load(); // refresh after returning
            },
            borderRadius: const BorderRadius.vertical(
                bottom: Radius.circular(14)),
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Icon(Icons.radar_rounded,
                      size: 16, color: AppTheme.terracotta),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'Auto-Detect / Change Server',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.terracotta,
                      ),
                    ),
                  ),
                  const Icon(Icons.chevron_right_rounded,
                      size: 18, color: AppTheme.slateLight),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
