import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../app/theme.dart';
import '../../auth/data/auth_repository.dart';
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
    super.dispose();
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
        SnackBar(content: Text('$safeName (${bytes.length} bytes)')),
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

    return Scaffold(
      appBar: AppBar(
        title: Text(
          listingId == null
              ? l.conversations
              : '${l.conversations} #$listingId',
        ),
      ),
      body: Column(
        children: [
          Expanded(child: _buildBody(l)),
          if (_pickedFiles.isNotEmpty) _buildPickedFilesStrip(),
          _buildComposer(l),
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
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
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

    final textBody = message['text_body']?.toString();
    final rawAttachments = message['attachments'];
    final attachments = _toMapList(rawAttachments);

    return Align(
      alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: isMine
                ? AppTheme.accent.withValues(alpha: 0.18)
                : AppTheme.bgMuted,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (textBody != null && textBody.trim().isNotEmpty)
                Padding(
                  padding: EdgeInsets.only(bottom: attachments.isEmpty ? 2 : 8),
                  child: Text(
                    textBody,
                    style: const TextStyle(fontSize: 14, height: 1.4),
                  ),
                ),
              if (attachments.isNotEmpty)
                ...attachments.map(_buildAttachmentWidget),
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  _messageTimeLabel(message),
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppTheme.textSubtle,
                  ),
                ),
              ),
            ],
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
                onPressed: _sending ? null : _pickFiles,
                icon: const Icon(Icons.attach_file),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: TextField(
                controller: _messageCtrl,
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
