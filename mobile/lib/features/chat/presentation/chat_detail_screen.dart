import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/theme.dart';
import '../../auth/data/auth_repository.dart';
import '../../reports/data/reports_repository.dart';
import '../data/chat_repository.dart';

class ChatDetailScreen extends ConsumerStatefulWidget {
  const ChatDetailScreen({
    super.key,
    required this.conversationId,
    this.initialConversation,
  });

  final int conversationId;
  final Map<String, dynamic>? initialConversation;

  @override
  ConsumerState<ChatDetailScreen> createState() => _ChatDetailScreenState();
}

class _ChatDetailScreenState extends ConsumerState<ChatDetailScreen> {
  final _messageCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final _composerFocusNode = FocusNode();
  final ImagePicker _imagePicker = ImagePicker();

  List<Map<String, dynamic>> _messages = [];
  Map<String, dynamic>? _conversation;
  List<PlatformFile> _pickedFiles = [];

  bool _loading = true;
  bool _loadingMore = false;
  bool _sending = false;
  String? _error;

  int _currentPage = 1;
  int? _myUserId;

  Timer? _pollTimer;
  final Set<int> _downloadingAttachmentIds = <int>{};

  @override
  void initState() {
    super.initState();
    _conversation = widget.initialConversation == null
        ? null
        : Map<String, dynamic>.from(widget.initialConversation!);
    _bootstrap();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _messageCtrl.dispose();
    _scrollCtrl.dispose();
    _composerFocusNode.dispose();
    super.dispose();
  }

  String _normalizePhoneForDialer(String rawPhone) {
    final trimmed = rawPhone.trim();
    final hasLeadingPlus = trimmed.startsWith('+');
    final digitsOnly = trimmed.replaceAll(RegExp(r'\D'), '');
    if (digitsOnly.isEmpty) {
      return '';
    }
    return hasLeadingPlus ? '+$digitsOnly' : digitsOnly;
  }

  Future<void> _callCounterpart(String phone) async {
    final l = S.of(context)!;
    final normalized = _normalizePhoneForDialer(phone);
    if (normalized.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.counterpartPhoneMissing)));
      return;
    }

    try {
      final uri = Uri(scheme: 'tel', path: normalized);
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened && mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(l.cannotOpenDialer)));
      }
    } catch (_) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l.cannotOpenDialer)));
    }
  }

  void _focusComposer() {
    _scrollToBottom(animate: true);
    FocusScope.of(context).requestFocus(_composerFocusNode);
  }

  Future<void> _bootstrap() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final chatRepo = ref.read(chatRepositoryProvider);
      final authRepo = ref.read(authRepositoryProvider);

      final meFuture = authRepo.getMe();
      final conversationFuture = chatRepo.getConversation(
        widget.conversationId,
      );

      final me = await meFuture;
      final conversation = await conversationFuture;

      if (!mounted) {
        return;
      }

      _myUserId = (me['id'] as num?)?.toInt();
      _conversation = conversation;

      await _loadLatestMessages(showLoader: true);
      _startPolling();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (!mounted || _loading || _sending) {
        return;
      }
      _refreshSilently();
    });
  }

  Future<void> _refreshSilently() async {
    try {
      await _loadLatestMessages(showLoader: false, animateScroll: false);
    } catch (_) {}
  }

  List<Map<String, dynamic>> _toMapList(dynamic rawItems) {
    if (rawItems is! List) {
      return <Map<String, dynamic>>[];
    }
    return rawItems
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<void> _loadLatestMessages({
    required bool showLoader,
    bool animateScroll = true,
  }) async {
    if (showLoader) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final repo = ref.read(chatRepositoryProvider);

      final firstPage = await repo.listMessages(
        conversationId: widget.conversationId,
        page: 1,
        pageSize: 30,
        markRead: true,
      );

      final totalPagesRaw = (firstPage['total_pages'] as num?)?.toInt() ?? 0;

      List<Map<String, dynamic>> items = _toMapList(firstPage['items']);
      var currentPage = 1;

      if (totalPagesRaw > 1) {
        final latestPage = await repo.listMessages(
          conversationId: widget.conversationId,
          page: totalPagesRaw,
          pageSize: 30,
          markRead: false,
        );
        items = _toMapList(latestPage['items']);
        currentPage = totalPagesRaw;
      }

      if (!mounted) {
        return;
      }

      setState(() {
        _messages = items;
        _currentPage = currentPage;
        _loading = false;
        _loadingMore = false;
        _error = null;
      });

      _scrollToBottom(animate: animateScroll);
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _loadingMore = false;
        _error = e.toString();
      });
      rethrow;
    }
  }

  Future<void> _loadOlderMessages() async {
    if (_loading || _loadingMore || _currentPage <= 1) {
      return;
    }

    setState(() {
      _loadingMore = true;
    });

    try {
      final targetPage = _currentPage - 1;
      final data = await ref
          .read(chatRepositoryProvider)
          .listMessages(
            conversationId: widget.conversationId,
            page: targetPage,
            pageSize: 30,
            markRead: false,
          );
      final older = _toMapList(data['items']);

      if (!mounted) {
        return;
      }

      setState(() {
        _messages = <Map<String, dynamic>>[...older, ..._messages];
        _currentPage = targetPage;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadingMore = false;
      });
    }
  }

  Future<void> _refresh() async {
    await _loadLatestMessages(showLoader: false);
  }

  Future<void> _pickFiles() async {
    final picked = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: <String>['jpg', 'jpeg', 'png', 'webp', 'pdf'],
    );
    if (picked == null || picked.files.isEmpty) {
      return;
    }

    final currentPaths = _pickedFiles
        .map((file) => file.path)
        .whereType<String>()
        .toSet();

    final nextFiles = picked.files.where((file) {
      final path = file.path;
      return path != null && path.isNotEmpty && !currentPaths.contains(path);
    }).toList();

    if (nextFiles.isEmpty) {
      return;
    }

    setState(() {
      _pickedFiles = <PlatformFile>[..._pickedFiles, ...nextFiles];
    });
  }

  Future<void> _pickFromGallery() async {
    final pickedImages = await _imagePicker.pickMultiImage(imageQuality: 88);
    if (pickedImages.isEmpty) {
      return;
    }

    final currentPaths = _pickedFiles
        .map((file) => file.path)
        .whereType<String>()
        .toSet();

    final nextFiles = <PlatformFile>[];
    for (final image in pickedImages) {
      final path = image.path;
      if (path.isEmpty || currentPaths.contains(path)) {
        continue;
      }

      var size = 0;
      try {
        size = await File(path).length();
      } catch (_) {}

      nextFiles.add(PlatformFile(name: image.name, path: path, size: size));
    }

    if (nextFiles.isEmpty) {
      return;
    }

    setState(() {
      _pickedFiles = <PlatformFile>[..._pickedFiles, ...nextFiles];
    });
  }

  Future<void> _showAttachSheet() async {
    final l = S.of(context)!;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black.withValues(alpha: 0.28),
      builder: (sheetContext) {
        return SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: <Color>[
                    AppTheme.bgSurface,
                    AppTheme.bgMuted.withValues(alpha: 0.96),
                  ],
                ),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: AppTheme.border),
                boxShadow: <BoxShadow>[
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.08),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 40,
                        height: 4,
                        decoration: BoxDecoration(
                          color: AppTheme.border,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      l.attachFile,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _buildAttachmentSourceAction(
                      icon: Icons.photo_library_outlined,
                      label: l.pickImages,
                      onTap: () async {
                        Navigator.of(sheetContext).pop();
                        await _pickFromGallery();
                      },
                    ),
                    const SizedBox(height: 8),
                    _buildAttachmentSourceAction(
                      icon: Icons.insert_drive_file_outlined,
                      label: l.pickFile,
                      onTap: () async {
                        Navigator.of(sheetContext).pop();
                        await _pickFiles();
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildAttachmentSourceAction({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return Material(
      color: AppTheme.white.withValues(alpha: 0.9),
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: AppTheme.bgMuted,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 18, color: AppTheme.accent),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Icon(
                Icons.chevron_right,
                size: 20,
                color: AppTheme.textSubtle,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _showMessageReportSheet(int messageId) async {
    final l = S.of(context)!;
    final reasonCtrl = TextEditingController();
    var selectedReason = 'spam';
    var submitting = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (sheetContext, setSheetState) {
            final reasons = <String, String>{
              'spam': l.spam,
              'scam': l.scam,
              'offensive': l.offensive,
              'other': l.other,
            };

            return Padding(
              padding: EdgeInsets.fromLTRB(
                16,
                16,
                16,
                MediaQuery.of(sheetContext).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    l.reportMessage,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selectedReason,
                    decoration: InputDecoration(labelText: l.reportReason),
                    items: reasons.entries
                        .map(
                          (entry) => DropdownMenuItem<String>(
                            value: entry.key,
                            child: Text(entry.value),
                          ),
                        )
                        .toList(),
                    onChanged: submitting
                        ? null
                        : (value) {
                            if (value == null) {
                              return;
                            }
                            setSheetState(() {
                              selectedReason = value;
                            });
                          },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: reasonCtrl,
                    maxLines: 3,
                    enabled: !submitting,
                    decoration: InputDecoration(labelText: l.description),
                  ),
                  const SizedBox(height: 14),
                  ElevatedButton(
                    onPressed: submitting
                        ? null
                        : () async {
                            final messenger = ScaffoldMessenger.of(context);
                            final details = reasonCtrl.text.trim();
                            if (details.isEmpty) {
                              messenger.showSnackBar(
                                SnackBar(content: Text(l.fieldRequired)),
                              );
                              return;
                            }

                            setSheetState(() {
                              submitting = true;
                            });

                            try {
                              await ref
                                  .read(reportsRepositoryProvider)
                                  .createReport(
                                    targetType: 'message',
                                    targetId: messageId,
                                    reasonCode: selectedReason,
                                    reasonText: details,
                                  );

                              if (!context.mounted) {
                                return;
                              }

                              if (sheetContext.mounted) {
                                Navigator.pop(sheetContext);
                              }
                              messenger.showSnackBar(
                                SnackBar(content: Text(l.reportSubmitted)),
                              );
                            } on DioException catch (e) {
                              final data = e.response?.data;
                              var message = l.errorOccurred;
                              if (data is Map && data['detail'] is String) {
                                message = data['detail'].toString();
                              }
                              if (context.mounted) {
                                messenger.showSnackBar(
                                  SnackBar(content: Text(message)),
                                );
                              }
                            } catch (_) {
                              if (context.mounted) {
                                messenger.showSnackBar(
                                  SnackBar(content: Text(l.errorOccurred)),
                                );
                              }
                            } finally {
                              if (sheetContext.mounted) {
                                setSheetState(() {
                                  submitting = false;
                                });
                              }
                            }
                          },
                    child: submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(l.apply),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    reasonCtrl.dispose();
  }

  Future<void> _showMessageActions(Map<String, dynamic> message) async {
    final messageId = (message['id'] as num?)?.toInt();
    if (messageId == null) {
      return;
    }

    final l = S.of(context)!;
    await showModalBottomSheet<void>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.flag_outlined),
                title: Text(l.reportMessage),
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _showMessageReportSheet(messageId);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  void _removePickedFile(int index) {
    setState(() {
      _pickedFiles = List<PlatformFile>.from(_pickedFiles)..removeAt(index);
    });
  }

  Future<void> _send() async {
    final l = S.of(context)!;
    final text = _messageCtrl.text.trim();
    final filePaths = _pickedFiles
        .map((file) => file.path)
        .whereType<String>()
        .toList();

    if (text.isEmpty && filePaths.isEmpty) {
      return;
    }

    setState(() {
      _sending = true;
    });

    try {
      final repo = ref.read(chatRepositoryProvider);

      if (filePaths.isEmpty) {
        await repo.sendTextMessage(
          conversationId: widget.conversationId,
          textBody: text,
        );
      } else {
        await repo.sendMessageWithAttachments(
          conversationId: widget.conversationId,
          textBody: text.isEmpty ? null : text,
          filePaths: filePaths,
        );
      }

      _messageCtrl.clear();
      setState(() {
        _pickedFiles = <PlatformFile>[];
      });

      await _loadLatestMessages(showLoader: false);
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
          _sending = false;
        });
      }
    }
  }

  Future<void> _downloadAttachment(Map<String, dynamic> attachment) async {
    final l = S.of(context)!;
    final attachmentId = (attachment['id'] as num?)?.toInt();
    if (attachmentId == null) {
      return;
    }

    setState(() {
      _downloadingAttachmentIds.add(attachmentId);
    });

    try {
      final bytes = await ref
          .read(chatRepositoryProvider)
          .downloadAttachmentBytes(attachmentId);
      final originalName =
          attachment['original_name']?.toString() ?? 'attachment_$attachmentId';
      final safeName = _safeFileName(originalName);
      final targetPath = '${Directory.systemTemp.path}/$safeName';
      final file = File(targetPath);
      await file.writeAsBytes(bytes, flush: true);

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.attachmentDownloaded(safeName, bytes.length))),
      );
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
          _downloadingAttachmentIds.remove(attachmentId);
        });
      }
    }
  }

  String _safeFileName(String value) {
    return value.replaceAll(RegExp(r'[<>:"/\\|?*]+'), '_');
  }

  String _friendlyError(Object error, S l) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }

        final errorNode = data['error'];
        if (errorNode is Map && errorNode['message'] != null) {
          return errorNode['message'].toString();
        }
      }

      if (error.message != null && error.message!.trim().isNotEmpty) {
        return error.message!;
      }
    }
    return l.errorOccurred;
  }

  void _scrollToBottom({required bool animate}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) {
        return;
      }

      final max = _scrollCtrl.position.maxScrollExtent;
      if (animate) {
        _scrollCtrl.animateTo(
          max,
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOut,
        );
      } else {
        _scrollCtrl.jumpTo(max);
      }
    });
  }

  String _messageTimeLabel(Map<String, dynamic> message) {
    final raw = message['sent_at']?.toString();
    if (raw == null || raw.isEmpty) {
      return '';
    }

    final date = DateTime.tryParse(raw);
    if (date == null) {
      return '';
    }

    final local = date.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;
    final listingId = (_conversation?['listing_id'] as num?)?.toInt();
    final listingTitle = _conversation?['listing_title']?.toString().trim();
    final hasListingTitle = listingTitle != null && listingTitle.isNotEmpty;
    final counterpartName = _conversation?['counterpart_name']
        ?.toString()
        .trim();
    final counterpartPhone = _conversation?['counterpart_phone']
        ?.toString()
        .trim();
    final hasCounterpartPhone =
        counterpartPhone != null && counterpartPhone.isNotEmpty;
    final chatTitle = hasListingTitle
        ? listingTitle
        : listingId == null
        ? l.conversations
        : '${l.listingDetail} #$listingId';

    return Scaffold(
      appBar: AppBar(title: Text(chatTitle)),
      body: Column(
        children: [
          if (hasCounterpartPhone)
            _buildContactPanel(
              l,
              phone: counterpartPhone,
              name: (counterpartName != null && counterpartName.isNotEmpty)
                  ? counterpartName
                  : null,
            ),
          Expanded(child: _buildBody(l)),
          if (_pickedFiles.isNotEmpty) _buildPickedFilesStrip(),
          _buildComposer(l),
        ],
      ),
    );
  }

  Widget _buildContactPanel(S l, {required String phone, String? name}) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.bgSurface,
        borderRadius: BorderRadius.circular(AppTheme.cardRadius),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (name != null) ...[
            Text(
              name,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 2),
          ],
          Text(
            '${l.phone}: $phone',
            style: const TextStyle(fontSize: 13, color: AppTheme.textSubtle),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _focusComposer,
                  icon: const Icon(Icons.chat_bubble_outline),
                  label: Text(l.writeAction),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: () => _callCounterpart(phone),
                  icon: const Icon(Icons.call_outlined),
                  label: Text(l.callAction),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBody(S l) {
    if (_loading && _messages.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    if (_error != null && _messages.isEmpty) {
      return Center(
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
            ElevatedButton(onPressed: _bootstrap, child: Text(l.retry)),
          ],
        ),
      );
    }

    if (_messages.isEmpty) {
      return RefreshIndicator(
        onRefresh: _refresh,
        color: AppTheme.accent,
        child: ListView(
          children: [
            SizedBox(
              height: 300,
              child: Center(
                child: Text(
                  l.noMessages,
                  style: const TextStyle(color: AppTheme.textSubtle),
                ),
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      color: AppTheme.accent,
      child: NotificationListener<ScrollNotification>(
        onNotification: (notification) {
          if (notification.metrics.pixels < 110) {
            _loadOlderMessages();
          }
          return false;
        },
        child: ListView.builder(
          controller: _scrollCtrl,
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 14),
          itemCount: _messages.length + (_loadingMore ? 1 : 0),
          itemBuilder: (context, index) {
            if (_loadingMore && index == 0) {
              return const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Center(
                  child: CircularProgressIndicator(
                    color: AppTheme.accent,
                    strokeWidth: 2,
                  ),
                ),
              );
            }

            final message = _messages[index - (_loadingMore ? 1 : 0)];
            return _buildMessageBubble(message);
          },
        ),
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> message) {
    final senderId = (message['sender_id'] as num?)?.toInt();
    final isMine = _myUserId != null && senderId == _myUserId;
    final screenWidth = MediaQuery.of(context).size.width;
    final bubbleMaxWidth = screenWidth >= 700 ? 520.0 : screenWidth * 0.78;

    final textBody = message['text_body']?.toString();
    final hasTextBody = textBody != null && textBody.trim().isNotEmpty;
    final rawAttachments = message['attachments'];
    final attachments = _toMapList(rawAttachments);
    final bubbleRadius = BorderRadius.only(
      topLeft: const Radius.circular(14),
      topRight: const Radius.circular(14),
      bottomLeft: Radius.circular(isMine ? 14 : 4),
      bottomRight: Radius.circular(isMine ? 4 : 14),
    );

    return Align(
      alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: GestureDetector(
          onLongPress: () => _showMessageActions(message),
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: bubbleMaxWidth, minWidth: 96),
            child: Container(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
              decoration: BoxDecoration(
                color: isMine
                    ? AppTheme.accent.withValues(alpha: 0.17)
                    : AppTheme.white,
                borderRadius: bubbleRadius,
                border: Border.all(color: AppTheme.border),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (hasTextBody)
                    Padding(
                      padding: EdgeInsets.only(
                        bottom: attachments.isEmpty ? 0 : 8,
                      ),
                      child: Text(
                        textBody,
                        style: const TextStyle(fontSize: 14, height: 1.38),
                      ),
                    ),
                  if (attachments.isNotEmpty)
                    ...attachments.map(_buildAttachmentWidget),
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: Text(
                        _messageTimeLabel(message),
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppTheme.textSubtle,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAttachmentWidget(Map<String, dynamic> attachment) {
    final mime = attachment['mime_type']?.toString() ?? '';
    final attachmentId = (attachment['id'] as num?)?.toInt();

    if (attachmentId == null) {
      return const SizedBox.shrink();
    }

    if (mime.startsWith('image/')) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: GestureDetector(
          onTap: () => _downloadAttachment(attachment),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: _InlineImageAttachment(attachmentId: attachmentId),
          ),
        ),
      );
    }

    final originalName = attachment['original_name']?.toString() ?? 'file';
    final isDownloading = _downloadingAttachmentIds.contains(attachmentId);

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: isDownloading ? null : () => _downloadAttachment(attachment),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isDownloading ? Icons.downloading : Icons.attach_file,
                  size: 18,
                  color: AppTheme.accent,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    originalName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.accent,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPickedFilesStrip() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: const BoxDecoration(
        color: AppTheme.bgSurface,
        border: Border(top: BorderSide(color: AppTheme.border)),
      ),
      child: SizedBox(
        height: 40,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: _pickedFiles.length,
          separatorBuilder: (context, index) => const SizedBox(width: 8),
          itemBuilder: (context, index) {
            final file = _pickedFiles[index];
            final name = file.name;

            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppTheme.bgMuted,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: AppTheme.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.insert_drive_file_outlined, size: 16),
                  const SizedBox(width: 6),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 140),
                    child: Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                  const SizedBox(width: 4),
                  GestureDetector(
                    onTap: () => _removePickedFile(index),
                    child: const Icon(
                      Icons.close,
                      size: 16,
                      color: AppTheme.textSubtle,
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildComposer(S l) {
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: const BoxDecoration(
        color: AppTheme.bgSurface,
        border: Border(top: BorderSide(color: AppTheme.border)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            SizedBox(
              width: 48,
              height: 48,
              child: IconButton(
                tooltip: l.attachFile,
                onPressed: _sending ? null : _showAttachSheet,
                icon: const Icon(Icons.attach_file),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: TextField(
                controller: _messageCtrl,
                focusNode: _composerFocusNode,
                enabled: !_sending,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.newline,
                decoration: InputDecoration(
                  hintText: l.typeMessage,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 48,
              height: 48,
              child: IconButton.filled(
                onPressed: _sending ? null : _send,
                icon: _sending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.send),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InlineImageAttachment extends ConsumerStatefulWidget {
  const _InlineImageAttachment({required this.attachmentId});

  final int attachmentId;

  @override
  ConsumerState<_InlineImageAttachment> createState() =>
      _InlineImageAttachmentState();
}

class _InlineImageAttachmentState
    extends ConsumerState<_InlineImageAttachment> {
  late Future<Uint8List> _future;

  @override
  void initState() {
    super.initState();
    _future = ref
        .read(chatRepositoryProvider)
        .downloadAttachmentBytes(widget.attachmentId);
  }

  @override
  void didUpdateWidget(covariant _InlineImageAttachment oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.attachmentId != widget.attachmentId) {
      _future = ref
          .read(chatRepositoryProvider)
          .downloadAttachmentBytes(widget.attachmentId);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uint8List>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Container(
            height: 170,
            width: double.infinity,
            color: AppTheme.bgMuted,
            alignment: Alignment.center,
            child: const CircularProgressIndicator(
              color: AppTheme.accent,
              strokeWidth: 2,
            ),
          );
        }

        if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
          return Container(
            height: 120,
            width: double.infinity,
            color: AppTheme.bgMuted,
            alignment: Alignment.center,
            child: const Icon(
              Icons.broken_image_outlined,
              color: AppTheme.textSubtle,
              size: 28,
            ),
          );
        }

        return Image.memory(
          snapshot.data!,
          fit: BoxFit.cover,
          width: double.infinity,
          height: 190,
        );
      },
    );
  }
}
