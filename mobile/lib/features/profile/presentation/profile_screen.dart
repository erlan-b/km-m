import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';
import 'package:km_marketplace/core/l10n/locale_controller.dart';

import '../../../app/theme.dart';
import '../../../core/storage/secure_storage.dart';
import '../../auth/data/auth_repository.dart';
import '../../auth/data/auth_state.dart';
import '../../auth/presentation/widgets/guest_auth_prompt.dart';
import '../data/profile_repository.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _error;
  Map<String, dynamic>? _me;
  late final ProviderSubscription<AuthState> _authSubscription;

  bool _isUnauthorized(Object error) {
    if (error is! DioException) {
      return false;
    }

    final statusCode = error.response?.statusCode;
    return statusCode == 401 || statusCode == 403;
  }

  void _handleAuthStateChange(AuthState? previous, AuthState next) {
    if (!mounted) {
      return;
    }

    if (next.status == AuthStatus.authenticated) {
      _load();
      return;
    }

    if (next.status == AuthStatus.unauthenticated) {
      setState(() {
        _loading = false;
        _saving = false;
        _error = null;
        _me = null;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    _authSubscription = ref.listenManual<AuthState>(
      authProvider,
      _handleAuthStateChange,
    );

    final authState = ref.read(authProvider);
    if (authState.status == AuthStatus.authenticated) {
      _load();
      return;
    }

    _loading = false;
  }

  @override
  void dispose() {
    _authSubscription.close();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final me = await ref.read(profileRepositoryProvider).getMyProfile();
      await ref
          .read(localeControllerProvider.notifier)
          .setLocaleByCode(me['preferred_language']?.toString());
      if (!mounted) {
        return;
      }
      setState(() {
        _me = me;
        _loading = false;
      });
    } catch (e) {
      if (_isUnauthorized(e)) {
        await ref.read(authProvider.notifier).logout();
        return;
      }

      if (!mounted) {
        return;
      }

      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  String _friendlyError(Object error, S l) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] is String) {
        return data['detail'].toString();
      }
      if (error.message != null && error.message!.trim().isNotEmpty) {
        return error.message!;
      }
    }
    return l.errorOccurred;
  }

  Future<void> _pickAvatar() async {
    if (_saving) {
      return;
    }

    final l = S.of(context)!;
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 86,
    );
    if (picked == null) {
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      final updated = await ref
          .read(profileRepositoryProvider)
          .uploadAvatar(picked.path);
      if (!mounted) {
        return;
      }

      setState(() {
        _me = updated;
      });

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.profileUpdated)));
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _showEditProfileSheet() async {
    final me = _me;
    if (me == null || _saving) {
      return;
    }

    final draft = await showModalBottomSheet<_ProfileUpdateDraft>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: AppTheme.bgMuted,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return _EditProfileSheet(initialProfile: me);
      },
    );

    if (draft == null) {
      return;
    }

    if (!mounted) {
      return;
    }

    final l = S.of(context)!;
    setState(() {
      _saving = true;
    });

    try {
      final updated = await ref
          .read(profileRepositoryProvider)
          .updateProfile(draft.toPayload());

      if (!mounted) {
        return;
      }

      setState(() {
        _me = updated;
      });

      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(S.of(context)!.profileUpdated)));
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  String _languageLabel(String code, S l) {
    return code == 'ru' ? l.languageRussian : l.languageEnglish;
  }

  Future<void> _showLanguageSheet() async {
    final me = _me;
    if (me == null || _saving) {
      return;
    }

    final l = S.of(context)!;
    final currentCode =
        (me['preferred_language']?.toString().toLowerCase() == 'ru')
        ? 'ru'
        : 'en';

    final selectedCode = await showModalBottomSheet<String>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: AppTheme.bgMuted,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return DecoratedBox(
          decoration: const BoxDecoration(
            color: AppTheme.bgMuted,
            borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
          ),
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  title: Text(
                    l.language,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                ListTile(
                  title: Text(l.languageEnglish),
                  trailing: currentCode == 'en'
                      ? const Icon(Icons.check, color: AppTheme.accent)
                      : null,
                  onTap: () => Navigator.of(sheetContext).pop('en'),
                ),
                ListTile(
                  title: Text(l.languageRussian),
                  trailing: currentCode == 'ru'
                      ? const Icon(Icons.check, color: AppTheme.accent)
                      : null,
                  onTap: () => Navigator.of(sheetContext).pop('ru'),
                ),
              ],
            ),
          ),
        );
      },
    );

    if (selectedCode == null || selectedCode == currentCode || !mounted) {
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      final updated = await ref.read(profileRepositoryProvider).updateProfile({
        'preferred_language': selectedCode,
      });

      if (!mounted) {
        return;
      }

      setState(() {
        _me = updated;
      });

      await ref
          .read(localeControllerProvider.notifier)
          .setLocaleByCode(selectedCode);
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _showGuestLanguageSheet() async {
    if (_saving) {
      return;
    }

    final l = S.of(context)!;
    final locale = ref.read(localeControllerProvider);
    final currentCode = (locale?.languageCode.toLowerCase() == 'ru')
        ? 'ru'
        : 'en';

    final selectedCode = await showModalBottomSheet<String>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: AppTheme.bgMuted,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return DecoratedBox(
          decoration: const BoxDecoration(
            color: AppTheme.bgMuted,
            borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
          ),
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  title: Text(
                    l.language,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                ListTile(
                  title: Text(l.languageEnglish),
                  trailing: currentCode == 'en'
                      ? const Icon(Icons.check, color: AppTheme.accent)
                      : null,
                  onTap: () => Navigator.of(sheetContext).pop('en'),
                ),
                ListTile(
                  title: Text(l.languageRussian),
                  trailing: currentCode == 'ru'
                      ? const Icon(Icons.check, color: AppTheme.accent)
                      : null,
                  onTap: () => Navigator.of(sheetContext).pop('ru'),
                ),
              ],
            ),
          ),
        );
      },
    );

    if (selectedCode == null || selectedCode == currentCode || !mounted) {
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      await ref
          .read(localeControllerProvider.notifier)
          .setLocaleByCode(selectedCode);
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _showSellerRoleRequestSheet() async {
    final me = _me;
    if (me == null || _saving) {
      return;
    }

    final currentSellerType =
        me['seller_type']?.toString().toLowerCase() ?? 'owner';
    final draft = await showModalBottomSheet<_SellerTypeChangeRequestDraft>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: AppTheme.bgMuted,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return _SellerTypeChangeRequestSheet(
          currentSellerType: currentSellerType,
        );
      },
    );

    if (draft == null || !mounted) {
      return;
    }

    final l = S.of(context)!;
    setState(() {
      _saving = true;
    });

    try {
      await ref
          .read(profileRepositoryProvider)
          .submitSellerTypeChangeRequest(
            requestedSellerType: draft.requestedSellerType,
            requestedCompanyName: draft.requestedCompanyName,
            note: draft.note,
            documentPaths: draft.documentPaths,
          );

      if (!mounted) {
        return;
      }

      await _load();

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        SnackBar(content: Text(S.of(context)!.changeRoleRequestSent)),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(_friendlyError(e, l))));
    } finally {
      if (mounted) {
        setState(() {
          _saving = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    final storage = ref.read(secureStorageProvider);
    final refreshToken = await storage.readRefreshToken();

    if (refreshToken != null && refreshToken.isNotEmpty) {
      try {
        await ref.read(authRepositoryProvider).logout(refreshToken);
      } catch (_) {}
    }

    await ref.read(authProvider.notifier).logout();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;
    final authState = ref.watch(authProvider);

    if (authState.status == AuthStatus.unknown) {
      return Scaffold(
        appBar: AppBar(title: Text(l.profile)),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (!authState.isAuthenticated) {
      final locale = ref.watch(localeControllerProvider);
      final preferredLanguageCode = (locale?.languageCode.toLowerCase() == 'ru')
          ? 'ru'
          : 'en';

      return Scaffold(
        appBar: AppBar(title: Text(l.profile)),
        body: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            _ActionTile(
              icon: Icons.language_outlined,
              title: l.language,
              subtitle: _languageLabel(preferredLanguageCode, l),
              onTap: _showGuestLanguageSheet,
            ),
            const SizedBox(height: 12),
            GuestAuthPrompt(
              title: l.guestProfileTitle,
              message: l.guestProfileHint,
              icon: Icons.person_outline,
            ),
          ],
        ),
      );
    }

    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(l.profile)),
        body: const Center(
          child: CircularProgressIndicator(color: AppTheme.accent),
        ),
      );
    }

    if (_error != null || _me == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l.profile)),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.error_outline,
                size: 48,
                color: AppTheme.textSubtle,
              ),
              const SizedBox(height: 12),
              Text(l.errorOccurred),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _load, child: Text(l.retry)),
            ],
          ),
        ),
      );
    }

    final me = _me!;
    final displayName = me['full_name'] as String? ?? '-';
    final email = me['email'] as String? ?? '-';
    final city = me['city'] as String?;
    final preferredLanguageCode =
        (me['preferred_language']?.toString().toLowerCase() == 'ru')
        ? 'ru'
        : 'en';
    final profileImagePath = me['profile_image_url']?.toString();
    final profileImageUrl =
        (profileImagePath == null || profileImagePath.isEmpty)
        ? null
        : ref
              .read(profileRepositoryProvider)
              .absoluteMediaUrl(profileImagePath);

    return Scaffold(
      appBar: AppBar(title: Text(l.profile)),
      body: RefreshIndicator(
        onRefresh: _load,
        color: AppTheme.accent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: [
            Material(
              color: AppTheme.bgSurface,
              borderRadius: BorderRadius.circular(AppTheme.cardRadius),
              child: InkWell(
                borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                onTap: _saving ? null : _showEditProfileSheet,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppTheme.cardRadius),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Row(
                    children: [
                      Stack(
                        clipBehavior: Clip.none,
                        children: [
                          Material(
                            color: Colors.transparent,
                            shape: const CircleBorder(),
                            child: InkWell(
                              customBorder: const CircleBorder(),
                              onTap: _saving ? null : _pickAvatar,
                              child: CircleAvatar(
                                radius: 28,
                                backgroundColor: AppTheme.accent,
                                backgroundImage: profileImageUrl == null
                                    ? null
                                    : NetworkImage(profileImageUrl),
                                child: profileImageUrl != null
                                    ? null
                                    : Text(
                                        displayName.isNotEmpty
                                            ? displayName[0].toUpperCase()
                                            : '?',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 22,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                              ),
                            ),
                          ),
                          Positioned(
                            right: -6,
                            bottom: -6,
                            child: Material(
                              color: AppTheme.accent,
                              shape: const CircleBorder(),
                              child: InkWell(
                                customBorder: const CircleBorder(),
                                onTap: _saving ? null : _pickAvatar,
                                child: const Padding(
                                  padding: EdgeInsets.all(6),
                                  child: Icon(
                                    Icons.camera_alt_outlined,
                                    size: 14,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              displayName,
                              style: const TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              email,
                              style: const TextStyle(
                                color: AppTheme.textSubtle,
                                fontSize: 13,
                              ),
                            ),
                            if (city != null && city.trim().isNotEmpty) ...[
                              const SizedBox(height: 2),
                              Text(
                                city,
                                style: const TextStyle(
                                  color: AppTheme.textSubtle,
                                  fontSize: 13,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            _ActionTile(
              icon: Icons.storefront_outlined,
              title: l.myListings,
              subtitle: l.manageYourListings,
              onTap: () => context.push('/my-listings'),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.add_box_outlined,
              title: l.createListing,
              subtitle: l.publishNewOffer,
              onTap: () => context.push('/my-listings/create'),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.receipt_long_outlined,
              title: l.paymentHistory,
              subtitle: l.pay,
              onTap: () => context.push('/payments'),
            ),
            const SizedBox(height: 12),
            Text(
              l.settings,
              style: const TextStyle(
                color: AppTheme.textSubtle,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.language_outlined,
              title: l.language,
              subtitle: _languageLabel(preferredLanguageCode, l),
              onTap: _showLanguageSheet,
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.workspace_premium_outlined,
              title: l.requestRoleChange,
              subtitle: l.roleChangeRequestSubtitle,
              onTap: _showSellerRoleRequestSheet,
            ),
            const SizedBox(height: 8),
            _ActionTile(
              icon: Icons.logout,
              title: l.logout,
              subtitle: l.signOutFromAccount,
              iconColor: AppTheme.statusError,
              onTap: _logout,
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileUpdateDraft {
  const _ProfileUpdateDraft({
    required this.fullName,
    required this.city,
    required this.phone,
    required this.bio,
  });

  final String fullName;
  final String city;
  final String phone;
  final String bio;

  Map<String, dynamic> toPayload() {
    String? normalize(String value) {
      final trimmed = value.trim();
      if (trimmed.isEmpty) {
        return null;
      }
      return trimmed;
    }

    return {
      'full_name': fullName.trim(),
      'city': normalize(city),
      'phone': normalize(phone),
      'bio': normalize(bio),
    };
  }
}

class _EditProfileSheet extends StatefulWidget {
  const _EditProfileSheet({required this.initialProfile});

  final Map<String, dynamic> initialProfile;

  @override
  State<_EditProfileSheet> createState() => _EditProfileSheetState();
}

class _EditProfileSheetState extends State<_EditProfileSheet> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _cityCtrl;
  late final TextEditingController _phoneCtrl;
  late final TextEditingController _bioCtrl;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(
      text: widget.initialProfile['full_name']?.toString() ?? '',
    );
    _cityCtrl = TextEditingController(
      text: widget.initialProfile['city']?.toString() ?? '',
    );
    _phoneCtrl = TextEditingController(
      text: widget.initialProfile['phone']?.toString() ?? '',
    );
    _bioCtrl = TextEditingController(
      text: widget.initialProfile['bio']?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _cityCtrl.dispose();
    _phoneCtrl.dispose();
    _bioCtrl.dispose();
    super.dispose();
  }

  void _submit() {
    final l = S.of(context)!;
    final fullName = _nameCtrl.text.trim();
    if (fullName.length < 2) {
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(l.fieldRequired)));
      return;
    }

    Navigator.of(context).pop(
      _ProfileUpdateDraft(
        fullName: fullName,
        city: _cityCtrl.text,
        phone: _phoneCtrl.text,
        bio: _bioCtrl.text,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;

    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppTheme.bgMuted,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                l.editProfile,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _nameCtrl,
                decoration: InputDecoration(labelText: l.fullName),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _cityCtrl,
                decoration: InputDecoration(labelText: l.city),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _phoneCtrl,
                decoration: InputDecoration(labelText: l.phone),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _bioCtrl,
                decoration: InputDecoration(labelText: l.bio),
                maxLines: 3,
              ),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: _submit, child: Text(l.save)),
            ],
          ),
        ),
      ),
    );
  }
}

class _SellerTypeChangeRequestDraft {
  const _SellerTypeChangeRequestDraft({
    required this.requestedSellerType,
    required this.requestedCompanyName,
    required this.note,
    required this.documentPaths,
  });

  final String requestedSellerType;
  final String? requestedCompanyName;
  final String? note;
  final List<String> documentPaths;
}

class _SellerTypeChangeRequestSheet extends StatefulWidget {
  const _SellerTypeChangeRequestSheet({required this.currentSellerType});

  final String currentSellerType;

  @override
  State<_SellerTypeChangeRequestSheet> createState() =>
      _SellerTypeChangeRequestSheetState();
}

class _SellerTypeChangeRequestSheetState
    extends State<_SellerTypeChangeRequestSheet> {
  static const _allSellerTypes = <String>['owner', 'company'];

  late String _requestedSellerType;
  final TextEditingController _companyNameCtrl = TextEditingController();
  final TextEditingController _noteCtrl = TextEditingController();
  List<PlatformFile> _documents = <PlatformFile>[];

  List<String> _availableSellerTypes() {
    final normalizedCurrent = widget.currentSellerType.trim().toLowerCase();
    return _allSellerTypes
        .where((sellerType) => sellerType != normalizedCurrent)
        .toList();
  }

  bool get _requiresDocuments => _requestedSellerType == 'company';

  String _sellerTypeLabel(String sellerType, S l) {
    switch (sellerType) {
      case 'owner':
        return l.sellerTypeOwner;
      case 'company':
        return l.sellerTypeCompany;
      default:
        return sellerType;
    }
  }

  @override
  void initState() {
    super.initState();
    final availableSellerTypes = _availableSellerTypes();
    _requestedSellerType = availableSellerTypes.isNotEmpty
        ? availableSellerTypes.first
        : 'owner';
  }

  @override
  void dispose() {
    _companyNameCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDocuments() async {
    final picked = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'jpg', 'jpeg', 'png', 'webp'],
    );

    if (picked == null || picked.files.isEmpty) {
      return;
    }

    final existingPaths = _documents
        .map((file) => file.path)
        .whereType<String>()
        .toSet();

    final next = picked.files.where((file) {
      final path = file.path;
      return path != null && path.isNotEmpty && !existingPaths.contains(path);
    }).toList();

    if (next.isEmpty) {
      return;
    }

    setState(() {
      _documents = <PlatformFile>[..._documents, ...next];
    });
  }

  void _removeDocument(int index) {
    setState(() {
      _documents = List<PlatformFile>.from(_documents)..removeAt(index);
    });
  }

  void _submit() {
    final l = S.of(context)!;

    final requestedCompanyName = _companyNameCtrl.text.trim();
    if (_requestedSellerType == 'company' && requestedCompanyName.isEmpty) {
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(l.fieldRequired)));
      return;
    }

    final documentPaths = _documents
        .map((file) => file.path)
        .whereType<String>()
        .toList();
    if (_requiresDocuments && documentPaths.isEmpty) {
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(l.verificationDocumentsRequired)));
      return;
    }

    final note = _noteCtrl.text.trim();
    Navigator.of(context).pop(
      _SellerTypeChangeRequestDraft(
        requestedSellerType: _requestedSellerType,
        requestedCompanyName: requestedCompanyName.isEmpty
            ? null
            : requestedCompanyName,
        note: note.isEmpty ? null : note,
        documentPaths: documentPaths,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;
    final availableSellerTypes = _availableSellerTypes();

    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppTheme.bgMuted,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          8,
          16,
          MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                l.requestRoleChange,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                l.roleChangePendingHint,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSubtle,
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _requestedSellerType,
                decoration: InputDecoration(labelText: l.roleChangeTarget),
                items: availableSellerTypes
                    .map(
                      (sellerType) => DropdownMenuItem(
                        value: sellerType,
                        child: Text(_sellerTypeLabel(sellerType, l)),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _requestedSellerType = value;
                    if (_requestedSellerType != 'company') {
                      _companyNameCtrl.clear();
                    }
                  });
                },
              ),
              if (_requestedSellerType == 'company') ...[
                const SizedBox(height: 10),
                TextField(
                  controller: _companyNameCtrl,
                  decoration: InputDecoration(labelText: l.companyName),
                ),
              ],
              const SizedBox(height: 10),
              TextField(
                controller: _noteCtrl,
                decoration: InputDecoration(labelText: l.roleChangeComment),
                maxLines: 3,
              ),
              if (_requiresDocuments) ...[
                const SizedBox(height: 12),
                Text(
                  l.verificationDocuments,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _pickDocuments,
                  icon: const Icon(Icons.attach_file),
                  label: Text(l.addDocuments),
                ),
                if (_documents.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (var i = 0; i < _documents.length; i++)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: AppTheme.bgSurface,
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(color: AppTheme.border),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              ConstrainedBox(
                                constraints: const BoxConstraints(
                                  maxWidth: 170,
                                ),
                                child: Text(
                                  _documents[i].name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontSize: 12),
                                ),
                              ),
                              const SizedBox(width: 6),
                              GestureDetector(
                                onTap: () => _removeDocument(i),
                                child: const Icon(
                                  Icons.close,
                                  size: 16,
                                  color: AppTheme.textSubtle,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ],
              ],
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _submit,
                child: Text(l.requestRoleChange),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.iconColor,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppTheme.bgSurface,
      borderRadius: BorderRadius.circular(AppTheme.cardRadius),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.cardRadius),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppTheme.cardRadius),
            border: Border.all(color: AppTheme.border),
          ),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: (iconColor ?? AppTheme.accent).withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  icon,
                  size: 20,
                  color: iconColor ?? AppTheme.accent,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSubtle,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: AppTheme.textSubtle),
            ],
          ),
        ),
      ),
    );
  }
}
